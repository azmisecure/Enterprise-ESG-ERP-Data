import numpy as np
import pandas as pd
from .core import ids, fiscal, MONTHS, END
from .erp import fx_lookup


def _usd(ctx, dates, ccy):
    return fx_lookup(ctx, pd.DatetimeIndex(pd.to_datetime(dates)).to_period("M").astype(str), ccy)


def gen_finance(ctx):
    rng = ctx.rng("finance")
    le = ctx.get("legal_entities").set_index("legal_entity_id")
    fac = ctx.get("facilities").set_index("facility_id")
    cc = ctx.get("cost_centres")
    ccf = cc.groupby("facility_id").cost_centre_id.first()
    parts = []

    def post(src_ids, doc_dates, post_dates, le_ids, fac_ids, ccy, legs, desc, system, ref_prefix, qty=None, qunit=None):
        n = len(src_ids)
        je_ids = np.char.add(ref_prefix, np.arange(n).astype(str))
        for k, (acct, dr, cr) in enumerate(legs):
            parts.append(pd.DataFrame(dict(journal_entry_id=je_ids, line_no=k + 1, gl_account=acct if np.ndim(acct) else np.full(n, acct), legal_entity_id=le_ids, facility_id=fac_ids,
                                           posting_date=pd.to_datetime(post_dates), document_date=pd.to_datetime(doc_dates), debit_amount=np.round(np.nan_to_num(dr), 2),
                                           credit_amount=np.round(np.nan_to_num(cr), 2), currency=ccy, reference_document=src_ids, transaction_description=desc, source_system=system,
                                           quantity=(qty if (qty is not None and k == 0) else np.nan), quantity_unit=(qunit if (qunit is not None and k == 0) else None))))
    z = lambda n: np.zeros(n)
    ap = ctx.get("ap_invoices")
    n = len(ap); exp = np.where(ap.po_id.isna(), np.where(ap.get("service_category", pd.Series(index=ap.index)).fillna("") == "IT Services", "670000", "660000"), "205000")
    post(ap.invoice_id.values, ap.invoice_date, ap.posting_date, ap.legal_entity_id.values, ap.facility_id.values, ap.currency.values,
         [(exp, ap.net_amount.clip(lower=0), (-ap.net_amount).clip(lower=0)), ("175000", ap.tax_amount.clip(lower=0), (-ap.tax_amount).clip(lower=0)), ("200000", (-ap.gross_amount).clip(lower=0), ap.gross_amount.clip(lower=0))],
         "Supplier invoice " + ap.supplier_invoice_no.astype(str), "SAP_S4", "JE-AP-")
    grn = ctx.get("goods_receipts").merge(ctx.get("po_lines")[["po_line_id", "unit_price", "currency"]], on="po_line_id")
    gv = grn.accepted_qty * grn.unit_price
    post(grn.grn_id.values, grn.receipt_date, grn.posting_date, grn.facility_id.map(fac.legal_entity_id).values, grn.facility_id.values, grn.currency.values,
         [("120000", gv, z(len(grn))), ("205000", z(len(grn)), gv)], "Goods receipt " + grn.sap_mblnr, "SAP_S4", "JE-GR-")
    pay = ctx.get("ap_payments").merge(ap[["invoice_id", "legal_entity_id", "facility_id"]], on="invoice_id", how="left")
    post(pay.payment_id.values, pay.payment_date, pay.payment_date, pay.legal_entity_id.values, pay.facility_id.values, pay.currency.values,
         [("200000", pay.amount, z(len(pay))), ("100100", z(len(pay)), pay.amount)], "Payment " + pay.payment_voucher, "SAP_S4", "JE-PY-")
    ar = ctx.get("ar_invoices")
    post(ar.ar_invoice_id.values, ar.invoice_date, ar.invoice_date, ar.legal_entity_id.values, None, ar.currency.values,
         [("110000", ar.gross_amount, z(len(ar))), ("400000", z(len(ar)), ar.net_amount), ("215000", z(len(ar)), ar.tax_amount)], "Customer invoice " + ar.sap_vbrk, "SAP_S4", "JE-AR-")
    rc = ctx.get("ar_receipts").merge(ar[["ar_invoice_id", "legal_entity_id"]], on="ar_invoice_id")
    post(rc.receipt_id.values, rc.receipt_date, rc.receipt_date, rc.legal_entity_id.values, None, rc.currency.values,
         [("100100", rc.amount, z(len(rc))), ("110000", z(len(rc)), rc.amount)], "Customer receipt", "SAP_S4", "JE-RC-")
    ui = ctx.get("utility_invoices")
    acct = ui.utility_type.map({"electricity": "600100", "natural_gas": "600200", "steam": "600400", "water": "600500", "chilled_water": "600400"}).values
    q = ui.consumption.values.copy()
    k = rng.choice(len(ui), int(len(ui) * 0.03), replace=False)
    q[k] = np.round(q[k] * rng.choice([0.9, 1.1, 1.18], len(k)), 2)
    net = ui.energy_charge + ui.network_charge
    post(ui.utility_invoice_id.values, ui.invoice_date, ui.invoice_date + pd.Timedelta(days=2), ui.facility_id.map(fac.legal_entity_id).values, ui.facility_id.values, ui.currency.values,
         [(acct, net, z(len(ui))), ("175000", ui.taxes, z(len(ui))), ("200000", z(len(ui)), ui.total_payable)], "Utility bill " + ui.invoice_number + " " + ui.utility_type, "SAP_S4", "JE-UT-", qty=q, qunit=ui.unit.values)
    fu = ctx.get("fuel_purchases")
    post(fu.fuel_purchase_id.values, fu.delivery_date, fu.delivery_date, fu.facility_id.map(fac.legal_entity_id).values, fu.facility_id.values, "USD",
         [(np.where(fu.fuel_type == "coal", "600800", "600300"), fu.amount_usd, z(len(fu))), ("200000", z(len(fu)), fu.amount_usd)], "Fuel delivery " + fu.fuel_type, "SAP_S4", "JE-FU-", qty=fu.quantity.values, qunit=fu.unit.values)
    ff = ctx.get("fleet_fuel")
    fm = ff.groupby(["facility_id", "period", "fuel_type"]).fuel_qty.sum().reset_index()
    fm = fm[fm.fuel_qty > 0].reset_index(drop=True)
    fq = fm.fuel_qty.values.copy()
    k2 = rng.choice(len(fm), int(len(fm) * 0.025), replace=False); fq[k2] = np.round(fq[k2] * rng.choice([0.85, 1.2, 1.35], len(k2)), 2)
    fd = pd.PeriodIndex(fm.period, freq="M").end_time.normalize()
    cost = np.round(fq * 1.45, 2)
    fm["fuel_card_statement_id"] = np.char.add("FCS-", np.arange(len(fm)).astype(str))
    post(fm.fuel_card_statement_id.values, fd, fd, fm.facility_id.map(fac.legal_entity_id).values, fm.facility_id.values, "USD",
         [("600300", cost, z(len(fm))), ("200000", z(len(fm)), cost)], "Fleet fuel card statement " + fm.fuel_type + " " + fm.period, "SAP_S4", "JE-FF-", qty=fq, qunit="L")
    fr = ctx.get("freight_invoices")
    sh = ctx.get("shipments").set_index("shipment_id")
    ofac = sh.origin.reindex(fr.shipment_id).values
    ofac = np.where(pd.Series(ofac).str.startswith("FAC").values, ofac, sh.destination.reindex(fr.shipment_id).values)
    post(fr.freight_invoice_id.values, fr.invoice_date, fr.invoice_date, pd.Series(ofac).map(fac.legal_entity_id).values, ofac, "USD",
         [("610000", fr.amount_usd, z(len(fr))), ("200000", z(len(fr)), fr.amount_usd)], "Freight " + fr["mode"], "SAP_S4", "JE-FR-")
    bt = ctx.get("business_travel")
    post(bt.trip_id.values, bt.travel_date, bt.travel_date + pd.Timedelta(days=7), bt.origin_facility_id.map(fac.legal_entity_id).values, bt.origin_facility_id.values, "USD",
         [("620000", bt.cost_usd, z(len(bt))), ("220000", z(len(bt)), bt.cost_usd)], "T&E " + bt.expense_report_id, "CONCUR_LIKE", "JE-TE-")
    wf = ctx.get("commuting_survey")
    pr = wf.loc[wf.index.repeat(12)].reset_index(drop=True); pr["m"] = np.tile(np.arange(1, 13), len(wf))
    pd_ = pd.to_datetime(pr.year.astype(str) + "-" + pr.m.astype(str) + "-28")
    sal = np.round(pr.fte * rng.uniform(3200, 5200, len(pr)) * (1 + 0.04 * (pr.year - 2022)), 2)
    post(np.char.add("PAY-", np.arange(len(pr)).astype(str)), pd_, pd_, pr.facility_id.map(fac.legal_entity_id).values, pr.facility_id.values, "USD",
         [("630000", sal, z(len(pr))), ("220000", z(len(pr)), sal)], "Payroll summary (aggregated)", "PAYROLL_LEGACY", "JE-PR-")
    ast = ctx.get("assets")
    dep = ast.groupby("facility_id").apply(lambda d: (d.acquisition_cost_usd / d.useful_life_years / 12).sum()).rename("m").reset_index()
    dp = dep.loc[dep.index.repeat(len(MONTHS))].reset_index(drop=True); dp["period"] = np.tile(MONTHS, len(dep))
    dd = dp.period.dt.end_time.dt.normalize()
    post(np.char.add("DEP-", np.arange(len(dp)).astype(str)), dd, dd, dp.facility_id.map(fac.legal_entity_id).values, dp.facility_id.values, "USD",
         [("640000", dp.m, z(len(dp))), ("159000", z(len(dp)), dp.m)], "Monthly depreciation run AFAB", "SAP_S4", "JE-DP-")
    les = le.index.values
    ic = pd.DataFrame(dict(period=np.repeat(MONTHS, 6), a=rng.choice(les, 6 * len(MONTHS)), b=rng.choice(les, 6 * len(MONTHS))))
    ic = ic[ic.a != ic.b].reset_index(drop=True); amt = np.round(rng.lognormal(12, 0.6, len(ic)), 2); idt = ic.period.dt.end_time.dt.normalize()
    post(np.char.add("IC-", np.arange(len(ic)).astype(str)), idt, idt, ic.a.values, None, "USD", [("165000", amt, z(len(ic))), ("401000", z(len(ic)), amt)], "Intercompany management fee", "SAP_S4", "JE-IC-")
    post(np.char.add("IC-", np.arange(len(ic)).astype(str)), idt, idt, ic.b.values, None, "USD", [("660000", amt, z(len(ic))), ("265000", z(len(ic)), amt)], "Intercompany management fee", "SAP_S4", "JE-ICB-")
    ac = ui[ui.utility_type == "electricity"].sample(frac=0.1, random_state=5)
    adt = pd.to_datetime(ac.billing_period_end)
    post(ac.utility_invoice_id.values, adt, adt, ac.facility_id.map(fac.legal_entity_id).values, ac.facility_id.values, ac.currency.values,
         [("600100", ac.energy_charge, z(len(ac))), ("210000", z(len(ac)), ac.energy_charge)], "Month-end electricity accrual", "SAP_S4", "JE-ACR-")
    gl = pd.concat(parts, ignore_index=True)
    gl = gl[(gl.debit_amount != 0) | (gl.credit_amount != 0)].reset_index(drop=True)
    gl["posting_date"] = gl.posting_date.clip(upper=END)
    n = len(gl)
    gl.insert(0, "gl_txn_id", ids("GL-", n, 8))
    gl["company_code"] = gl.legal_entity_id.map(le.company_code)
    fs = gl.legal_entity_id.map(le.fiscal_year_start_month).fillna(1).astype(int).values
    gl["fiscal_year"], gl["fiscal_period"] = fiscal(gl.posting_date, fs)
    gl["cost_centre_id"] = gl.facility_id.map(ccf)
    gl["profit_centre_id"] = gl.cost_centre_id.map(cc.set_index("cost_centre_id").profit_centre_id)
    gl["business_unit_id"] = gl.facility_id.map(fac.business_unit_id)
    rate = fx_lookup(ctx, gl.posting_date.dt.to_period("M").astype(str), gl.currency.values)
    gl["amount_usd"] = np.round((gl.debit_amount - gl.credit_amount) * rate, 2)
    gl["created_ts"] = gl.posting_date + pd.to_timedelta(rng.integers(8 * 3600, 20 * 3600, n), "s")
    gl["modified_ts"] = gl.created_ts
    gl["created_by_role"] = rng.choice(["AP Clerk", "AR Clerk", "GL Accountant", "Batch Job", "Interface"], n)
    # anomalies
    ut = gl.index[(gl.journal_entry_id.str.startswith("JE-UT-")) & (gl.line_no == 1)]
    src_q = ui.set_index("utility_invoice_id").consumption
    mism = ut[np.abs(gl.loc[ut, "quantity"].values - src_q.reindex(gl.loc[ut, "reference_document"]).values) > 0.01]
    ctx.anom("gl_transactions", gl.gl_txn_id.values[mism], "Cross-system inconsistency", "ERP electricity consumption differing from utility invoices", "Medium",
             src_q.reindex(gl.loc[mism, "reference_document"]).values, gl.quantity.values[mism], "Quantity re-keyed manually at invoice parking", "Reconcile ERP quantity to invoice",
             "Use invoice quantity", related=gl.reference_document.values[mism], ghg="Scope 1/2", system="SAP_S4")
    fl = gl.index[(gl.journal_entry_id.str.startswith("JE-FF-")) & (gl.line_no == 1)]
    jidx = gl.loc[fl, "journal_entry_id"].str.replace("JE-FF-", "").astype(int).values
    bad = np.isin(jidx, k2)
    ctx.anom("gl_transactions", gl.gl_txn_id.values[fl][bad], "Cross-system inconsistency", "Fuel quantities differing between fleet and finance systems", "Medium",
             fm.fuel_qty.values[jidx[bad]], gl.quantity.values[fl][bad], "Fuel card statement includes non-fleet purchases", "Fleet telematics vs finance reconciliation", "Investigate fuel card",
             related=gl.reference_document.values[fl][bad], ghg="Scope 1 Mobile", system="SAP_S4")
    wp = rng.choice(n, int(n * 0.002), replace=False)
    e = gl.posting_date.values[wp].copy()
    gl.loc[wp, "posting_date"] = pd.Series(pd.to_datetime(e) + pd.DateOffset(months=1)).clip(upper=END).values
    gl.loc[wp, "fiscal_year"], gl.loc[wp, "fiscal_period"] = fiscal(gl.posting_date.values[wp], fs[wp])
    ctx.anom("gl_transactions", gl.gl_txn_id.values[wp], "Temporal", "Transactions posted in incorrect financial periods", "Medium", pd.to_datetime(e).date, pd.to_datetime(gl.posting_date.values[wp]).date,
             "Period left open / late posting", "Posting date vs document date period check", "Repost in correct period", family="Data_Inconsistencies", system="SAP_S4")
    rm = rng.choice(np.where(gl.posting_date.dt.year == 2023)[0], 60, replace=False)
    e = gl.debit_amount.values[rm].copy(); gl.loc[rm, "debit_amount"] = np.round(e * 0.8, 2); gl.loc[rm, "modified_ts"] = pd.Timestamp("2025-03-14 22:10:00")
    ctx.anom("gl_transactions", gl.gl_txn_id.values[rm], "Governance", "Historical data retrospectively modified without audit records", "Critical", e, gl.debit_amount.values[rm],
             "Direct table update outside change control", "modified_ts >> created_ts with no audit event", "Reverse unauthorised change", family="Governance_Anomalies", system="SAP_S4")
    dj = rng.choice(gl.journal_entry_id.unique(), 150, replace=False)
    dup = gl[gl.journal_entry_id.isin(dj)].copy()
    dup["posting_date"] = (dup.posting_date + pd.DateOffset(months=12)).clip(upper=END); dup["gl_txn_id"] = ids("GL-", len(dup), 8, start=n + 1)
    dup["fiscal_year"], dup["fiscal_period"] = fiscal(dup.posting_date, dup.legal_entity_id.map(le.fiscal_year_start_month).fillna(1).astype(int).values)
    gl = pd.concat([gl, dup], ignore_index=True)
    ctx.anom("gl_transactions", dup.gl_txn_id.values, "Duplicate record", "Duplicate transactions across reporting periods", "High", "single posting", "re-posted 12 months later",
             "Interface replay after year-end", "Duplicate on reference document across years", "Reverse", related=dup.reference_document.values, family="Data_Inconsistencies", system="SAP_S4")
    ctx.lineage(gl, "SAP_S4", "FI-GL", "S4PRD", "ACDOCA", "Finance", gl.journal_entry_id.values)
    ctx.save(gl, "ERP/Finance/GL/gl_transactions.parquet", "gl_transactions", pk="gl_txn_id", fks={"gl_account": "chart_of_accounts.gl_account", "legal_entity_id": "legal_entities.legal_entity_id", "cost_centre_id": "cost_centres.cost_centre_id"}, target=2000000, system="SAP_S4")
    tb = gl.groupby(["company_code", "fiscal_year", "fiscal_period", "gl_account"]).agg(debit_usd=("amount_usd", lambda s: s.clip(lower=0).sum()), credit_usd=("amount_usd", lambda s: (-s).clip(lower=0).sum())).reset_index()
    tb["balance_usd"] = (tb.debit_usd - tb.credit_usd).round(2)
    ctx.save(tb, "ERP/Finance/GL/trial_balance.csv", "trial_balance", system="SAP_S4")
    coa = ctx.get("chart_of_accounts").set_index("gl_account")
    gl["year"] = gl.posting_date.dt.year
    gl["type"] = gl.gl_account.map(coa.account_type)
    pl = gl[gl.type.isin(["Revenue", "Expense"])].groupby(["legal_entity_id", "year", "gl_account"]).amount_usd.sum().reset_index()
    pl["gl_account_name"] = pl.gl_account.map(coa.gl_account_name); pl["line_amount_usd"] = -pl.amount_usd.round(2)
    ctx.save(pl.drop(columns=["amount_usd"]), "Finance/profit_and_loss_by_entity_year.csv", "profit_and_loss", system="SAP_S4")
    bs = gl[gl.type.isin(["Asset", "Liability", "Equity"])].groupby(["legal_entity_id", "year", "gl_account"]).amount_usd.sum().groupby(level=[0, 2]).cumsum().reset_index()
    bs["gl_account_name"] = bs.gl_account.map(coa.gl_account_name)
    ctx.save(bs.rename(columns={"amount_usd": "closing_balance_usd"}), "Finance/balance_sheet_by_entity_year.csv", "balance_sheet", system="SAP_S4")
    cl = pd.DataFrame([dict(company_code=c, fiscal_year=y, fiscal_period=p, close_status="Closed" if (y < 2026 or p < 12) else "Open", closed_on=(pd.Timestamp(f"{y}-01-01") + pd.DateOffset(months=p, days=6)).date())
                       for c in le.company_code for y in range(2022, 2027) for p in range(1, 13)])
    ctx.save(cl, "Finance/financial_period_closures.csv", "period_closures", system="SAP_S4")
