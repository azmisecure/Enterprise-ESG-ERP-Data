import numpy as np
import pandas as pd
from .core import ids, zipf, rand_dates, fiscal, START, END, DAYS
from .master import COUNTRIES, CO_IDX, DIV_MATS, GROUP_TO_CAT

SERVICE_CATS = ["IT Services", "Professional Services", "Facility Services", "Capital Equipment", "Travel Services", "Refrigeration Services", "Logistics", "Waste Management"]
CCY = {c[0]: c[3] for c in COUNTRIES}


def fx_lookup(ctx, periods, ccy):
    fx = ctx.get("fx_rates").set_index(["period", "currency"]).usd_per_unit
    return fx.reindex(pd.MultiIndex.from_arrays([np.asarray(periods), np.asarray(ccy)])).values


def price_index(groups, dates):
    t = (pd.DatetimeIndex(dates).year.values - 2022) + pd.DatetimeIndex(dates).month.values / 12
    shock = np.where(np.isin(groups, ["Metals", "Minerals"]), 0.28 * np.exp(-t / 0.9), 0.12 * np.exp(-t / 1.3))
    return (1 + 0.025 * t + shock)


def clip_active(dates, start, end):
    d = pd.Series(pd.DatetimeIndex(dates))
    s = pd.Series(pd.to_datetime(start)); e = pd.Series(pd.to_datetime(end))
    d = d.where(~(d < s) | s.isna(), s + pd.Timedelta(days=21))
    d = d.where(~(d > e) | e.isna(), e - pd.Timedelta(days=21))
    return d.clip(START, END).dt.normalize().values


def gen_procurement(ctx):
    rng = ctx.rng("procurement")
    sup, mat, fac = ctx.get("suppliers"), ctx.get("materials"), ctx.get("facilities")
    plants, cc = ctx.get("plants"), ctx.get("cost_centres")
    mfg = fac[fac.facility_type == "Manufacturing"].reset_index(drop=True)
    n_po = ctx.n(500000)
    svc = rng.random(n_po) < 0.18
    # contracts
    sw = zipf(len(sup), 0.9)
    ctr_sup = sup.iloc[np.unique(rng.choice(len(sup), 3500, p=sw))]
    k = rng.choice([1, 2, 3], len(ctr_sup), p=[.6, .3, .1])
    ctr = ctr_sup.loc[ctr_sup.index.repeat(k), ["supplier_id", "currency", "payment_terms"]].reset_index(drop=True)
    ctr.insert(0, "contract_id", ids("CTR-", len(ctr), 6))
    ctr["valid_from"] = pd.to_datetime(rng.choice(pd.date_range("2020-01-01", "2025-06-01"), len(ctr)))
    ctr["valid_to"] = ctr.valid_from + pd.to_timedelta(rng.choice([365, 730, 1095], len(ctr)), "D")
    ctr["contract_type"] = rng.choice(["Framework agreement", "Price agreement", "Service contract"], len(ctr))
    ctr["committed_value_usd"] = np.round(rng.lognormal(13, 1.2, len(ctr)), -2)
    ctr["sustainability_clause"] = rng.random(len(ctr)) < 0.35
    ctx.save(ctr, "Procurement/Purchase_Orders/supplier_contracts.parquet", "supplier_contracts", pk="contract_id", fks={"supplier_id": "suppliers.supplier_id"}, system="SAP_Ariba")
    # PO header
    m_idx = rng.choice(len(mat), n_po, p=zipf(len(mat), 0.7))
    m0 = mat.iloc[m_idx]
    sup_mat = np.where((rng.random(n_po) < 0.8) | m0.secondary_supplier_id.isna().values, m0.primary_supplier_id.values, m0.secondary_supplier_id.values)
    svc_sup = sup[sup.supplier_category.isin(SERVICE_CATS)]
    svc_pick = svc_sup.iloc[rng.choice(len(svc_sup), n_po, p=zipf(len(svc_sup), 0.8))]
    supplier = np.where(svc, svc_pick.supplier_id.values, sup_mat)
    fam_fac = {f: mfg[mfg.division_id.isin([d for d, ms in DIV_MATS.items() if f in ms])].facility_id.values for f in mat.material_family.unique()}
    facility = np.array([(fam_fac.get(f) if len(fam_fac.get(f, [])) else mfg.facility_id.values)[rng.integers(1000)] if False else None for f in []], dtype=object)
    facility = np.empty(n_po, dtype=object)
    for f, arr in fam_fac.items():
        sel = (m0.material_family.values == f)
        pool = arr if len(arr) else mfg.facility_id.values
        facility[sel] = pool[rng.integers(0, len(pool), sel.sum())]
    all_fac = fac.facility_id.values
    facility[svc] = all_fac[rng.integers(0, len(all_fac), svc.sum())]
    fi = fac.set_index("facility_id")
    s_i = sup.set_index("supplier_id")
    dates = rand_dates(rng, n_po)
    dates = clip_active(dates, fi.loc[facility, "commissioning_date"].values, fi.loc[facility, "divestment_date"].values)
    dates = clip_active(dates, s_i.loc[supplier, "onboarding_date"].values, s_i.loc[supplier, "termination_date"].values)
    po = pd.DataFrame(dict(po_id=ids("PO-", n_po, 7), sap_ebeln=(4500000000 + np.arange(n_po) * 3).astype(str), po_date=dates, supplier_id=supplier, facility_id=facility,
                           legal_entity_id=fi.loc[facility, "legal_entity_id"].values, po_type=np.where(svc, "Service", "Material"),
                           currency=s_i.loc[supplier, "currency"].values, payment_terms=s_i.loc[supplier, "payment_terms"].values,
                           incoterm=rng.choice(["FCA", "DAP", "DDP", "EXW", "CIF", "FOB"], n_po, p=[.25, .3, .15, .1, .1, .1])))
    po["plant_id"] = po.facility_id.map(plants.drop_duplicates("facility_id").set_index("facility_id").plant_id)
    cmap = ctr.groupby("supplier_id").contract_id.first()
    po["contract_id"] = po.supplier_id.map(cmap)
    po["pr_id"] = np.where(rng.random(n_po) < 0.93, ids("PR-", n_po, 7), None)
    po["approval_status"] = rng.choice(["Approved", "Approved", "Approved", "Approved with exception"], n_po)
    po["approval_date"] = po.po_date + pd.to_timedelta(rng.integers(0, 4, n_po), "D")
    po["approved_by_role"] = rng.choice(["Category Manager", "Plant Controller", "Procurement Director"], n_po, p=[.6, .3, .1])
    po["delivery_terms_days"] = rng.choice([7, 14, 21, 30, 45, 60], n_po)
    # lines
    nl = 1 + rng.poisson(2.0, n_po)
    li = np.repeat(np.arange(n_po), nl)
    nL = len(li)
    sup_mats = mat.groupby("primary_supplier_id").material_id.apply(np.array).to_dict()
    mi = mat.set_index("material_id")
    line_mat = np.empty(nL, dtype=object)
    lsup = po.supplier_id.values[li]
    first = np.r_[True, li[1:] != li[:-1]]
    line_mat[first] = m0.material_id.values[li[first]]
    r = rng.random(nL)
    for j in np.where(~first)[0]:
        arr = sup_mats.get(lsup[j])
        line_mat[j] = arr[int(r[j] * len(arr))] if arr is not None else line_mat[j - 1]
    lsvc = svc[li]
    line_mat[lsvc] = None
    unit = np.where(lsvc, "EA", mi.reindex(line_mat).base_unit.values)
    qmu = {"kg": (7.6, 1.0), "t": (3.2, 0.8), "pcs": (5.2, 1.0), "L": (6.2, 0.9), "m3": (6.0, 0.8), "EA": (0, 0)}
    qty = np.array([np.exp(qmu[u][0] + qmu[u][1] * z) if u != "EA" else 1 for u, z in zip(unit, rng.normal(0, 1, nL))])
    qty = np.where(np.isin(unit, ["pcs", "EA"]), np.ceil(qty), np.round(qty, 3))
    ldates = po.po_date.values[li]
    grp = mi.reindex(line_mat).material_group.fillna("Services").values
    usd = np.where(lsvc, np.round(rng.lognormal(9.0, 1.2, nL), 2), mi.reindex(line_mat).standard_price_usd.fillna(0).values * price_index(grp, ldates) * rng.lognormal(0, 0.05, nL))
    lccy = po.currency.values[li]
    rate = fx_lookup(ctx, pd.DatetimeIndex(ldates).to_period("M").astype(str), lccy)
    price = np.round(usd / rate, 4)
    disc = np.where(rng.random(nL) < 0.2, rng.choice([2, 3, 5], nL), 0)
    pol = pd.DataFrame(dict(po_line_id=np.char.add(po.po_id.values[li].astype(str), np.char.add("-", np.char.zfill((np.arange(nL) - np.maximum.accumulate(np.where(first, np.arange(nL), 0)) + 1).astype(str) if True else "", 3))),
                            po_id=po.po_id.values[li], line_no=(np.arange(nL) - np.maximum.accumulate(np.where(first, np.arange(nL), 0)) + 1) * 10,
                            material_id=line_mat, service_category=np.where(lsvc, s_i.loc[lsup, "supplier_category"].values, None),
                            order_qty=qty, unit=unit, unit_price=price, currency=lccy, discount_pct=disc))
    pol["net_amount"] = np.round(pol.order_qty * pol.unit_price * (1 - pol.discount_pct / 100), 2)
    pol["tax_rate_pct"] = rng.choice([0, 5, 10, 16, 18, 19, 20, 21], nL)
    pol["requested_delivery_date"] = ldates + pd.to_timedelta(po.delivery_terms_days.values[li], "D")
    pol["gl_account"] = np.where(lsvc, np.where(pol.service_category.values == "IT Services", "670000", np.where(pol.service_category.values == "Capital Equipment", "150000", "660000")), "120000")
    ccf = cc.groupby("facility_id").cost_centre_id.first()
    pol["cost_centre_id"] = po.facility_id.map(ccf).values[li]
    # duplicate PO anomaly
    po["total_net_amount"] = po.po_id.map(pol.groupby("po_id").net_amount.sum()).round(2)
    dpo = rng.choice(n_po, int(n_po * 0.004), replace=False)
    dup = po.iloc[dpo].copy(); dup["po_id"] = ids("PO-", len(dup), 7, start=n_po + 1); dup["sap_ebeln"] = (4600000000 + np.arange(len(dup))).astype(str)
    po = pd.concat([po, dup], ignore_index=True)
    ctx.save(pol, "ERP/Procurement/purchase_order_lines.parquet", "po_lines", pk="po_line_id", fks={"po_id": "purchase_orders.po_id", "material_id": "materials.material_id", "cost_centre_id": "cost_centres.cost_centre_id"}, target=1500000, system="SAP_S4")
    ctx.lineage(po, "SAP_S4", "MM-PUR", "S4PRD", "EKKO", "Procurement", po.sap_ebeln.values, ts_col="po_date")
    ctx.save(po, "ERP/Procurement/purchase_orders.parquet", "purchase_orders", pk="po_id", fks={"supplier_id": "suppliers.supplier_id", "facility_id": "facilities.facility_id", "contract_id": "supplier_contracts.contract_id"}, target=500000, system="SAP_S4")
    ctx.anom("purchase_orders", dup.po_id.values, "Duplicate record", "Duplicate purchase orders", "High", "No duplicate", po.po_id.values[dpo],
             "PO re-keyed after workflow timeout", "Fuzzy duplicate match on supplier, date, amount", "Cancel duplicate PO", related=po.po_id.values[dpo], process="Procure-to-pay", ghg="Scope 3 Cat 1")
    # GRN
    lead = np.where(np.asarray([CCY.get(c, "") for c in s_i.loc[lsup, "country_id"].fillna("XX").values]) == np.asarray([CCY[c] for c in fi.loc[po.facility_id.values[li], "country_id"].values]), rng.gamma(3, 4, nL), rng.gamma(4, 9, nL))
    split = (rng.random(nL) < 0.08) & ~lsvc
    gi = np.r_[np.arange(nL), np.where(split)[0]]
    frac = np.ones(len(gi)); frac[:nL][split] = 0.6; frac[nL:] = 0.4
    gdate = pd.DatetimeIndex(ldates[gi]) + pd.to_timedelta(lead[gi] + np.where(np.arange(len(gi)) >= nL, 18, 0), "D")
    rq = np.round(qty[gi] * frac * np.where(rng.random(len(gi)) < 0.04, rng.uniform(0.9, 0.99, len(gi)), 1.0), 3)
    rej = np.round(np.where(rng.random(len(gi)) < 0.03, rq * rng.uniform(0.01, 0.06, len(gi)), 0), 3)
    grn = pd.DataFrame(dict(grn_id=ids("GRN-", len(gi), 7), sap_mblnr=(5000000000 + np.arange(len(gi))).astype(str), po_id=pol.po_id.values[gi], po_line_id=pol.po_line_id.values[gi],
                            receipt_date=gdate.normalize(), posting_date=(gdate + pd.to_timedelta(rng.choice([0, 0, 0, 1, 2], len(gi)), "D")).normalize(),
                            facility_id=po.facility_id.values[li][gi], material_id=line_mat[gi], received_qty=rq, rejected_qty=rej, unit=unit[gi], movement_type="101",
                            storage_location=rng.choice(["RM01", "RM02", "QI01", "WH10"], len(gi)), batch_no=np.char.add("B", rng.integers(10 ** 6, 10 ** 7, len(gi)).astype(str))))
    grn["accepted_qty"] = grn.received_qty - grn.rejected_qty
    bad = pick = rng.choice(np.where(~lsvc[gi])[0], int(len(gi) * 0.012), replace=False)
    exp = grn.loc[bad, "received_qty"].values.copy()
    mult = rng.choice([1.25, 1.4, 0.6, 0.7], len(bad))
    grn.loc[bad, "received_qty"] = np.round(exp * mult, 3); grn.loc[bad, "accepted_qty"] = grn.loc[bad, "received_qty"] - grn.loc[bad, "rejected_qty"]
    ctx.lineage(grn, "SAP_S4", "MM-IM", "S4PRD", "MSEG", "Warehouse Operations", grn.sap_mblnr.values, ts_col="posting_date")
    ctx.save(grn, "ERP/Procurement/goods_receipts.parquet", "goods_receipts", pk="grn_id", fks={"po_line_id": "po_lines.po_line_id", "facility_id": "facilities.facility_id", "material_id": "materials.material_id"}, system="SAP_S4")
    ctx.anom("goods_receipts", grn.grn_id.values[bad], "Quantity mismatch", "Purchase order quantity differs from goods receipt", "Medium", exp, grn.loc[bad, "received_qty"].values,
             "Receiving clerk keyed delivery-note quantity incorrectly", "Three-way match tolerance check (±10%)", "Correct GRN quantity to delivery note", related=grn.po_line_id.values[bad], process="Procure-to-pay", ghg="Scope 3 Cat 1")
    # AP invoices
    acc = grn.groupby("po_id").agg(last_receipt=("receipt_date", "max"))
    acc_qty = grn.groupby("po_line_id").accepted_qty.sum()
    amt = pol.assign(acc=pol.po_line_id.map(acc_qty).fillna(pol.order_qty)).assign(v=lambda d: d.acc * d.unit_price * (1 - d.discount_pct / 100), t=lambda d: d.acc * d.unit_price * (1 - d.discount_pct / 100) * d.tax_rate_pct / 100).groupby("po_id")[["v", "t"]].sum()
    pos = po.iloc[:n_po]
    inv = pd.DataFrame(dict(invoice_id=ids("APINV-", n_po, 7), sap_belnr=(5100000000 + np.arange(n_po)).astype(str), supplier_invoice_no=np.char.add("SI-", rng.integers(10 ** 6, 10 ** 8, n_po).astype(str)),
                            supplier_id=pos.supplier_id.values, po_id=pos.po_id.values, facility_id=pos.facility_id.values, legal_entity_id=pos.legal_entity_id.values,
                            currency=pos.currency.values, payment_terms=pos.payment_terms.values))
    inv["invoice_date"] = (pd.to_datetime(inv.po_id.map(acc.last_receipt).fillna(pd.Series(pos.po_date.values, index=inv.index))) + pd.to_timedelta(rng.integers(0, 10, n_po), "D")).values
    inv["posting_date"] = inv.invoice_date + pd.to_timedelta(rng.choice([0, 1, 2, 3, 5], n_po), "D")
    inv["net_amount"] = inv.po_id.map(amt.v).round(2).values
    inv["tax_amount"] = inv.po_id.map(amt.t).round(2).values
    inv["document_type"] = "KR"
    pv = rng.choice(n_po, int(n_po * 0.02), replace=False)
    e_amt = inv.loc[pv, "net_amount"].values.copy()
    inv.loc[pv, "net_amount"] = np.round(e_amt * rng.uniform(1.06, 1.25, len(pv)), 2)
    wd = rng.choice(n_po, int(n_po * 0.004), replace=False)
    e_d = inv.loc[wd, "invoice_date"].values.copy()
    inv.loc[wd, "invoice_date"] = pd.to_datetime(e_d) - pd.DateOffset(years=1)
    ms = rng.choice(np.setdiff1d(np.arange(n_po), pv), int(n_po * 0.003), replace=False)
    e_s = inv.loc[ms, "supplier_id"].values.copy(); inv.loc[ms, "supplier_id"] = None
    inv["gross_amount"] = (inv.net_amount + inv.tax_amount).round(2)
    inv["invoice_status"] = np.where(rng.random(n_po) < 0.015, "Disputed", "Approved")
    inv["approval_date"] = inv.posting_date + pd.to_timedelta(rng.integers(0, 6, n_po), "D")
    di = rng.choice(n_po, int(n_po * 0.008), replace=False)
    dup = inv.iloc[di].copy(); dup["invoice_id"] = ids("APINV-", len(dup), 7, start=n_po + 1); dup["sap_belnr"] = (5190000000 + np.arange(len(dup))).astype(str)
    dup["posting_date"] = dup.posting_date + pd.to_timedelta(rng.integers(3, 40, len(dup)), "D")
    nonpo = int(n_po * 0.08)
    np_sup = svc_sup.iloc[rng.integers(0, len(svc_sup), nonpo)]
    npi = pd.DataFrame(dict(invoice_id=ids("APINV-", nonpo, 7, start=n_po + len(dup) + 1), sap_belnr=(5180000000 + np.arange(nonpo)).astype(str),
                            supplier_invoice_no=np.char.add("NP-", rng.integers(10 ** 6, 10 ** 8, nonpo).astype(str)), supplier_id=np_sup.supplier_id.values, po_id=None,
                            facility_id=all_fac[rng.integers(0, len(all_fac), nonpo)], currency=np_sup.currency.values, payment_terms=np_sup.payment_terms.values,
                            invoice_date=rand_dates(rng, nonpo), document_type="KR"))
    npi["legal_entity_id"] = npi.facility_id.map(fi.legal_entity_id)
    npi["posting_date"] = npi.invoice_date + pd.to_timedelta(rng.integers(0, 4, nonpo), "D")
    npi["net_amount"] = np.round(rng.lognormal(8.5, 1.3, nonpo) / fx_lookup(ctx, pd.DatetimeIndex(npi.invoice_date).to_period("M").astype(str), npi.currency), 2)
    npi["tax_amount"] = np.round(npi.net_amount * 0.15, 2); npi["gross_amount"] = npi.net_amount + npi.tax_amount
    npi["invoice_status"] = "Approved"; npi["approval_date"] = npi.posting_date
    npi["service_category"] = np_sup.supplier_category.values
    cn = inv.sample(int(n_po * 0.015), random_state=1).copy()
    cn["invoice_id"] = ids("APCN-", len(cn), 6); cn["document_type"] = "KG"; cn["sap_belnr"] = (5170000000 + np.arange(len(cn))).astype(str)
    cn["net_amount"] = -np.round(cn.net_amount * rng.uniform(0.02, 0.3, len(cn)), 2); cn["tax_amount"] = np.round(cn.net_amount * 0.15, 2); cn["gross_amount"] = cn.net_amount + cn.tax_amount
    cn["invoice_date"] = cn.invoice_date + pd.Timedelta(days=25); cn["posting_date"] = cn.invoice_date
    ap = pd.concat([inv, dup, npi, cn], ignore_index=True)
    ap["invoice_date"] = pd.to_datetime(ap.invoice_date).clip(upper=END); ap["posting_date"] = pd.to_datetime(ap.posting_date).clip(upper=END)
    fy_start = ap.legal_entity_id.map(ctx.get("legal_entities").set_index("legal_entity_id").fiscal_year_start_month).fillna(1).astype(int)
    ap["fiscal_year"], ap["fiscal_period"] = fiscal(ap.posting_date, fy_start.values)
    ap["company_code"] = ap.legal_entity_id.map(ctx.get("legal_entities").set_index("legal_entity_id").company_code)
    ctx.lineage(ap, "SAP_S4", "FI-AP", "S4PRD", "BKPF/BSEG", "Finance", ap.sap_belnr.values, ts_col="posting_date")
    ctx.save(ap, "ERP/Finance/AP/supplier_invoices.parquet", "ap_invoices", pk="invoice_id", fks={"supplier_id": "suppliers.supplier_id", "po_id": "purchase_orders.po_id", "facility_id": "facilities.facility_id"}, target=500000, system="SAP_S4")
    ctx.anom("ap_invoices", inv.invoice_id.values[pv], "Amount mismatch", "Supplier invoice amount differs from purchase order", "High", e_amt, inv.net_amount.values[pv],
             "Supplier billed unapproved price increase", "Three-way match (PO x GRN x invoice)", "Short-pay to PO price; raise debit note", related=inv.po_id.values[pv], process="Procure-to-pay", ghg="Scope 3 Cat 1 (spend-based)")
    ctx.anom("ap_invoices", inv.invoice_id.values[wd], "Temporal", "Incorrect transaction dates", "Medium", pd.to_datetime(e_d).date, pd.to_datetime(inv.invoice_date.values[wd]).date,
             "Year keyed incorrectly at invoice capture", "Invoice date precedes PO date", "Correct invoice year", related=inv.po_id.values[wd], process="Procure-to-pay", family="Data_Inconsistencies")
    ctx.anom("ap_invoices", inv.invoice_id.values[ms], "Missing data", "Missing supplier identifiers", "High", e_s, "NULL", "OCR capture failed to map vendor", "Required-field check",
             "Map vendor via PO reference", related=inv.po_id.values[ms], process="Procure-to-pay")
    ctx.anom("ap_invoices", dup.invoice_id.values, "Duplicate record", "Duplicate invoices", "Critical", "Single posting", inv.invoice_id.values[di], "Invoice received by email and EDI and posted twice",
             "Duplicate check on supplier invoice no. + amount", "Reverse duplicate posting", related=inv.invoice_id.values[di], process="Procure-to-pay", ghg="Scope 3 Cat 1 (double counting risk)")
    # payments
    pay_src = ap[(ap.document_type == "KR") & (ap.invoice_status == "Approved")]
    tdays = pay_src.payment_terms.str.extract(r"NET(\d+)")[0].astype(float).fillna(30).values
    pdt = pd.to_datetime(pay_src.invoice_date.values) + pd.to_timedelta(tdays + rng.normal(2, 8, len(pay_src)).round(), "D")
    keep = pdt <= END
    pay = pd.DataFrame(dict(payment_id=ids("APPAY-", keep.sum(), 7), invoice_id=pay_src.invoice_id.values[keep], supplier_id=pay_src.supplier_id.values[keep], payment_date=pdt[keep].normalize(),
                            amount=pay_src.gross_amount.values[keep], currency=pay_src.currency.values[keep], payment_method=rng.choice(["SEPA", "ACH", "SWIFT", "Local transfer"], keep.sum()),
                            payment_voucher=np.char.add("PV", (8000000 + np.arange(keep.sum())).astype(str))))
    ctx.save(pay, "ERP/Finance/AP/ap_payments.parquet", "ap_payments", pk="payment_id", fks={"invoice_id": "ap_invoices.invoice_id"}, system="SAP_S4")
    perf = grn.assign(q=pd.PeriodIndex(grn.receipt_date, freq="Q").astype(str), sup=grn.po_id.map(po.set_index("po_id").supplier_id), late=(grn.receipt_date > grn.po_line_id.map(pol.set_index("po_line_id").requested_delivery_date)))
    sp = perf.groupby(["sup", "q"]).agg(receipts=("grn_id", "count"), late_receipts=("late", "sum"), rejected_qty=("rejected_qty", "sum"), received_qty=("received_qty", "sum")).reset_index().rename(columns={"sup": "supplier_id", "q": "quarter"})
    sp["on_time_pct"] = np.round(100 * (1 - sp.late_receipts / sp.receipts), 1); sp["rejection_pct"] = np.round(100 * sp.rejected_qty / sp.received_qty.clip(lower=1e-6), 2)
    sp.insert(0, "performance_record_id", ids("SPR-", len(sp), 6))
    ctx.save(sp, "Procurement/Supplier_Assessments/supplier_performance_quarterly.parquet", "supplier_performance", pk="performance_record_id", fks={"supplier_id": "suppliers.supplier_id"}, system="SAP_Ariba")


def gen_sales(ctx):
    rng = ctx.rng("sales")
    cust, prod, fac = ctx.get("customers"), ctx.get("products"), ctx.get("facilities")
    n_lines = ctx.n(1000000)
    n_so = int(n_lines / 2.5)
    seg_div = {"Automotive OEM": ["DIV-AUT", "DIV-MET"], "Industrial OEM": ["DIV-IMC", "DIV-ELE", "DIV-MET", "DIV-CHM"], "Construction Contractor": ["DIV-CON", "DIV-MET"],
               "Utility": ["DIV-ELE"], "Distributor": ["DIV-IMC", "DIV-AUT", "DIV-ELE", "DIV-PKG", "DIV-CHM", "DIV-CON"], "Government": ["DIV-CON", "DIV-ELE"],
               "Packaging Converter": ["DIV-PKG", "DIV-CHM"], "EPC Contractor": ["DIV-ELE", "DIV-CON", "DIV-IMC"]}
    ci = rng.choice(len(cust), n_so, p=zipf(len(cust), 0.85))
    c = cust.iloc[ci]
    so_dates = clip_active(rand_dates(rng, n_so), c.acquisition_date.values, c.churn_date.values)
    so = pd.DataFrame(dict(sales_order_id=ids("SO-", n_so, 7), crm_order_ref=np.char.add("8010SYN", rng.choice(10 ** 9, n_so, replace=False).astype(str)),
                           sap_vbeln=(1000000 + np.arange(n_so)).astype(str), customer_id=c.customer_id.values, order_date=so_dates, sales_territory=c.sales_territory.values,
                           incoterm=c.incoterm.values, currency=[CCY[x] for x in c.country_id.values], channel=rng.choice(["Direct", "Distributor", "E-portal", "Tender"], n_so, p=[.5, .25, .15, .1])))
    nl = np.clip(rng.poisson(1.5, n_so) + 1, 1, 8)
    li = np.repeat(np.arange(n_so), nl)
    nL = len(li)
    pdiv = prod.groupby("division_id").apply(lambda d: d.index.values).to_dict()
    seg = c.segment.values[li]
    pi = np.empty(nL, dtype=int)
    rr = rng.random(nL)
    for s, divs in seg_div.items():
        sel = np.where(seg == s)[0]
        pool = np.concatenate([pdiv[d] for d in divs])
        w = zipf(len(pool), 0.6)
        pi[sel] = pool[rng.choice(len(pool), len(sel), p=w)]
    p = prod.iloc[pi]
    unit = p.sales_unit.values
    base_q = np.where(unit == "t", rng.lognormal(3.5, 0.9, nL), np.where(unit == "kg", rng.lognormal(7.5, 1.0, nL), np.where(p.list_price_usd.values > 20000, rng.integers(1, 4, nL), np.where(p.list_price_usd.values > 1000, rng.lognormal(1.8, 0.7, nL), rng.lognormal(5.5, 1.1, nL)))))
    qty = np.where(unit == "pcs", np.ceil(base_q), np.round(base_q, 2))
    ld = so.order_date.values[li]
    rate = fx_lookup(ctx, pd.DatetimeIndex(ld).to_period("M").astype(str), so.currency.values[li])
    price = np.round(p.list_price_usd.values * price_index(np.full(nL, "x"), ld) * rng.uniform(0.82, 1.0, nL) / rate, 4)
    first = np.r_[True, li[1:] != li[:-1]]
    lno = (np.arange(nL) - np.maximum.accumulate(np.where(first, np.arange(nL), 0)) + 1)
    sol = pd.DataFrame(dict(so_line_id=[f"{a}-{b:03d}" for a, b in zip(so.sales_order_id.values[li], lno)], sales_order_id=so.sales_order_id.values[li], line_no=lno * 10,
                            product_id=p.product_id.values, order_qty=qty, sales_unit=unit, unit_price=price, currency=so.currency.values[li]))
    sol["net_amount"] = np.round(sol.order_qty * sol.unit_price, 2)
    mfg = fac[fac.facility_type == "Manufacturing"]
    dfac = {d: g.facility_id.values for d, g in mfg.groupby("division_id")}
    sol["ship_from_facility_id"] = [dfac[d][k % len(dfac[d])] for d, k in zip(p.division_id.values, rng.integers(0, 1000, nL))]
    so["net_value"] = so.sales_order_id.map(sol.groupby("sales_order_id").net_amount.sum()).round(2)
    ctx.lineage(so, "SALESFORCE", "Sales Cloud", "SFDC", "Order", "Sales", so.crm_order_ref.values, ts_col="order_date")
    ctx.save(so, "CRM/Orders/sales_orders.parquet", "sales_orders", pk="sales_order_id", fks={"customer_id": "customers.customer_id"}, system="SALESFORCE")
    ctx.save(sol, "CRM/Orders/sales_order_lines.parquet", "so_lines", pk="so_line_id", fks={"sales_order_id": "sales_orders.sales_order_id", "product_id": "products.product_id", "ship_from_facility_id": "facilities.facility_id"}, target=1000000, system="SALESFORCE")
    # deliveries
    part = rng.random(nL) < 0.06
    di = np.r_[np.arange(nL), np.where(part)[0]]
    frac = np.ones(len(di)); frac[:nL][part] = 0.55; frac[nL:] = 0.45
    ddate = pd.DatetimeIndex(ld[di]) + pd.to_timedelta(rng.gamma(3, 5, len(di)) + np.where(np.arange(len(di)) >= nL, 20, 0), "D")
    dl = pd.DataFrame(dict(delivery_id=ids("DLV-", len(di), 7), sap_likp=(80000000 + np.arange(len(di))).astype(str), so_line_id=sol.so_line_id.values[di],
                           sales_order_id=sol.sales_order_id.values[di], customer_id=so.customer_id.values[li][di], product_id=sol.product_id.values[di],
                           ship_from_facility_id=sol.ship_from_facility_id.values[di], delivery_date=pd.Series(ddate.normalize()).clip(upper=END).values, delivered_qty=np.round(qty[di] * frac, 2),
                           sales_unit=unit[di], gross_weight_kg=np.round(qty[di] * frac * p.unit_weight_kg.values[di] * 1.04, 2)))
    dl["on_time"] = rng.random(len(di)) < 0.91
    ctx.save(dl, "CRM/Deliveries/deliveries.parquet", "deliveries", pk="delivery_id", fks={"so_line_id": "so_lines.so_line_id", "customer_id": "customers.customer_id"}, system="SAP_S4")
    # AR invoices
    up = sol.unit_price.values[di]
    ar = pd.DataFrame(dict(ar_invoice_id=ids("ARINV-", len(di), 7), sap_vbrk=(90000000 + np.arange(len(di))).astype(str), delivery_id=dl.delivery_id.values,
                           sales_order_id=dl.sales_order_id.values, customer_id=dl.customer_id.values, invoice_date=dl.delivery_date.values,
                           net_amount=np.round(dl.delivered_qty.values * up, 2), currency=sol.currency.values[di]))
    ar["tax_amount"] = np.round(ar.net_amount * rng.choice([0, 0.1, 0.19, 0.2], len(ar)), 2)
    ar["gross_amount"] = ar.net_amount + ar.tax_amount
    ar["legal_entity_id"] = dl.ship_from_facility_id.map(fac.set_index("facility_id").legal_entity_id).values
    ar["due_date"] = ar.invoice_date + pd.Timedelta(days=45)
    ctx.lineage(ar, "SAP_S4", "SD-BIL", "S4PRD", "VBRK", "Finance", ar.sap_vbrk.values, ts_col="invoice_date")
    ctx.save(ar, "CRM/Invoices/sales_invoices.parquet", "ar_invoices", pk="ar_invoice_id", fks={"delivery_id": "deliveries.delivery_id", "customer_id": "customers.customer_id"}, target=500000, system="SAP_S4")
    pdt = pd.to_datetime(ar.due_date) + pd.to_timedelta(rng.normal(3, 15, len(ar)).round(), "D")
    keep = (pdt <= END) & (rng.random(len(ar)) > 0.02)
    arp = pd.DataFrame(dict(receipt_id=ids("ARREC-", keep.sum(), 7), ar_invoice_id=ar.ar_invoice_id.values[keep], customer_id=ar.customer_id.values[keep],
                            receipt_date=pdt[keep].dt.normalize().values, amount=ar.gross_amount.values[keep], currency=ar.currency.values[keep],
                            allocation_status=rng.choice(["Fully allocated", "Partially allocated"], keep.sum(), p=[.97, .03])))
    ctx.save(arp, "ERP/Finance/AR/customer_payments.parquet", "ar_receipts", pk="receipt_id", fks={"ar_invoice_id": "ar_invoices.ar_invoice_id"}, system="SAP_S4")
    od = ar[~keep].copy(); od["days_overdue"] = (END - pd.to_datetime(od.due_date)).dt.days.clip(lower=0)
    ctx.save(od[["ar_invoice_id", "customer_id", "gross_amount", "currency", "due_date", "days_overdue"]], "ERP/Finance/AR/open_receivables_2026-12-31.csv", "open_receivables", system="SAP_S4")
    ret = dl.sample(int(len(dl) * 0.018), random_state=3)
    rt = pd.DataFrame(dict(return_id=ids("RET-", len(ret), 6), delivery_id=ret.delivery_id.values, customer_id=ret.customer_id.values, product_id=ret.product_id.values,
                           return_date=(pd.to_datetime(ret.delivery_date) + pd.to_timedelta(rng.integers(5, 60, len(ret)), "D")).clip(upper=END).values,
                           returned_qty=np.round(ret.delivered_qty.values * rng.uniform(0.05, 1, len(ret)), 2), reason=rng.choice(["Damaged", "Wrong spec", "Quality defect", "Over-delivery"], len(ret)),
                           credit_note_id=ids("ARCN-", len(ret), 6)))
    ctx.save(rt, "CRM/Sales/customer_returns.parquet", "customer_returns", pk="return_id", fks={"delivery_id": "deliveries.delivery_id"}, system="SALESFORCE")
    cp = dl.sample(int(len(dl) * 0.01), random_state=4)
    ctx.save(pd.DataFrame(dict(complaint_id=ids("CMP-", len(cp), 6), delivery_id=cp.delivery_id.values, customer_id=cp.customer_id.values, opened_date=cp.delivery_date.values,
                               category=rng.choice(["Late delivery", "Quality", "Documentation", "Packaging", "Carbon data request"], len(cp)), status=rng.choice(["Closed", "Open", "Escalated"], len(cp), p=[.8, .15, .05]))),
             "CRM/Sales/customer_complaints.csv", "customer_complaints", pk="complaint_id", system="SALESFORCE")
    no = ctx.n(150000)
    oc = cust.iloc[rng.choice(len(cust), no, p=zipf(len(cust), 0.6))]
    ctx.save(pd.DataFrame(dict(opportunity_id=ids("OPP-", no, 6), customer_id=oc.customer_id.values, created_date=rand_dates(rng, no), stage=rng.choice(["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won", "Closed Lost"], no, p=[.1, .1, .15, .1, .3, .25]),
                               amount_usd=np.round(rng.lognormal(11, 1.3, no), -2), division_id=rng.choice([d for d in pdiv], no), sustainability_requirement_flag=rng.random(no) < 0.22)),
             "CRM/Sales/opportunities.parquet", "opportunities", pk="opportunity_id", fks={"customer_id": "customers.customer_id"}, system="SALESFORCE")
    fc = sol.assign(m=pd.DatetimeIndex(ld).to_period("M").astype(str), d=p.division_id.values, usd=sol.net_amount.values * rate).groupby(["d", "m"]).usd.sum().reset_index()
    fc["forecast_usd"] = np.round(fc.usd.shift(1).bfill() * rng.uniform(0.92, 1.1, len(fc)), 0)
    ctx.save(fc.rename(columns={"d": "division_id", "m": "period", "usd": "actual_usd"}), "CRM/Sales/sales_forecasts.csv", "sales_forecasts", system="SALESFORCE")
    top = cust.iloc[:3000]
    ctx.save(pd.DataFrame(dict(customer_contract_id=ids("CCTR-", 3000, 5), customer_id=top.customer_id.values, start_date=pd.to_datetime(rng.choice(pd.date_range("2020-01-01", "2025-01-01"), 3000)),
                               term_months=rng.choice([12, 24, 36], 3000), pcf_disclosure_required=rng.random(3000) < 0.3, recycled_content_min_pct=np.where(rng.random(3000) < 0.2, rng.choice([20, 30, 50], 3000), None))),
             "CRM/Sales/customer_contracts.csv", "customer_contracts", pk="customer_contract_id", system="SALESFORCE")


def gen_manufacturing(ctx):
    rng = ctx.rng("manufacturing")
    prod, bom, rt, lines, fac = ctx.get("products"), ctx.get("bom"), ctx.get("routings"), ctx.get("production_lines"), ctx.get("facilities")
    assets, mat = ctx.get("assets"), ctx.get("materials")
    sol = ctx.get("so_lines")
    n_o = ctx.n(150000)
    pw = sol.product_id.value_counts()
    rt_p = rt[rt.product_id.isin(pw.index)].drop_duplicates("product_id")
    w = pw.reindex(rt_p.product_id).values.astype(float); w /= w.sum()
    r = rt_p.iloc[rng.choice(len(rt_p), n_o, p=w)]
    p = prod.set_index("product_id").loc[r.product_id]
    fi = fac.set_index("facility_id")
    start = clip_active(rand_dates(rng, n_o), fi.loc[r.facility_id, "commissioning_date"].values, fi.loc[r.facility_id, "divestment_date"].values)
    unit = p.sales_unit.values
    planned = np.where(unit == "t", np.round(rng.lognormal(4.5, 0.6, n_o), 1), np.where(unit == "kg", np.round(rng.lognormal(8.5, 0.7, n_o)), np.where(p.unit_weight_kg.values > 300, rng.integers(1, 12, n_o), np.ceil(rng.lognormal(6.2, 0.8, n_o)))))
    yld = np.clip(rng.beta(30, 1.6, n_o), 0.75, 1.0)
    actual = np.where(unit == "pcs", np.floor(planned * yld), np.round(planned * yld, 2))
    hrs = np.round(planned * r.cycle_time_min.values / 60 / np.maximum(1, planned / 400), 2) + 2
    po = pd.DataFrame(dict(production_order_id=ids("PRO-", n_o, 7), sap_aufnr=(10000000 + np.arange(n_o)).astype(str), mes_order_ref=np.char.add("MES-WO-", rng.choice(10 ** 8, n_o, replace=False).astype(str)),
                           product_id=r.product_id.values, routing_id=r.routing_id.values, production_line_id=r.production_line_id.values, plant_id=r.plant_id.values,
                           facility_id=r.facility_id.values, planned_start=start, planned_qty=planned, actual_qty=actual, unit=unit,
                           scrap_qty=np.round(planned - actual, 2), yield_pct=np.round(100 * actual / np.maximum(planned, 1e-9), 2), run_hours=hrs,
                           energy_kwh_standard=np.round(actual * r.energy_kwh_per_unit.values, 2)))
    po["actual_finish"] = po.planned_start + pd.to_timedelta(np.ceil(hrs / 16) + rng.integers(0, 3, n_o), "D")
    po["order_status"] = np.where(po.actual_finish > END, "Released", "Technically completed")
    po["standard_cost_usd"] = np.round(actual * p.list_price_usd.values * 0.62, 2)
    po["actual_cost_usd"] = np.round(po.standard_cost_usd * rng.lognormal(0.01, 0.05, n_o), 2)
    po["cost_variance_usd"] = po.actual_cost_usd - po.standard_cost_usd
    ctx.lineage(po, "SAP_S4", "PP", "S4PRD", "AUFK", "Operations", po.sap_aufnr.values, ts_col="planned_start")
    ctx.save(po, "ERP/Inventory/production_orders.parquet", "production_orders", pk="production_order_id", fks={"product_id": "products.product_id", "production_line_id": "production_lines.production_line_id", "facility_id": "facilities.facility_id"}, target=1000000, system="SAP_S4")
    cf = po[["production_order_id", "actual_finish", "actual_qty", "scrap_qty", "run_hours"]].copy()
    cf.insert(0, "confirmation_id", ids("CNF-", len(cf), 7)); cf["confirmed_by_shift"] = rng.choice(["A", "B", "C"], len(cf))
    ctx.save(cf, "Manufacturing/Production/production_confirmations.parquet", "production_confirmations", pk="confirmation_id", fks={"production_order_id": "production_orders.production_order_id"}, system="MES")
    mc = po[["production_order_id", "product_id", "facility_id", "planned_start", "actual_qty"]].merge(bom[["product_id", "material_id", "component_qty_per_unit", "component_unit", "scrap_allowance_pct"]], on="product_id")
    mc["standard_qty"] = np.round(mc.actual_qty * mc.component_qty_per_unit * (1 + mc.scrap_allowance_pct / 100), 4)
    mc["consumed_qty"] = np.round(mc.standard_qty * rng.lognormal(0.005, 0.025, len(mc)), 4)
    mc.insert(0, "consumption_id", ids("MCON-", len(mc), 8))
    mc["movement_type"] = "261"
    ab = rng.choice(len(mc), int(len(mc) * 0.006), replace=False)
    e = mc.consumed_qty.values[ab].copy(); mc.loc[ab, "consumed_qty"] = np.round(e * rng.uniform(1.35, 2.2, len(ab)), 4)
    ctx.save(mc.drop(columns=["component_qty_per_unit", "scrap_allowance_pct", "actual_qty", "product_id"]).rename(columns={"planned_start": "posting_date", "component_unit": "unit"}),
             "ERP/Inventory/material_consumption.parquet", "material_consumption", pk="consumption_id", fks={"production_order_id": "production_orders.production_order_id", "material_id": "materials.material_id"}, system="SAP_S4")
    ctx.anom("material_consumption", mc.consumption_id.values[ab], "Operational", "Abnormal material wastage", "Medium", e, mc.consumed_qty.values[ab], "Unreported scrap / process upset",
             "Consumption vs BOM standard variance > 30%", "Investigate line; book scrap", related=mc.production_order_id.values[ab], process="Manufacturing", ghg="Scope 3 Cat 1", family="Operational_Anomalies")
    # MES daily line performance
    lf = lines.merge(fac[["facility_id", "commissioning_date", "temporary_shutdown_start", "temporary_shutdown_end", "divestment_date", "energy_intensity_index"]], on="facility_id")
    L, D = len(lf), len(DAYS)
    li = np.repeat(np.arange(L), D); di = np.tile(np.arange(D), L)
    dd = DAYS[di]
    alive = (dd >= pd.DatetimeIndex(lf.commissioning_date.values[li]))
    shut = (dd >= pd.DatetimeIndex(lf.temporary_shutdown_start.values[li])) & (dd <= pd.DatetimeIndex(lf.temporary_shutdown_end.values[li]))
    wk = np.array([1, 1, 1, 1, 1, .55, .15])[dd.dayofweek]
    seas = np.array([.92, .95, 1.02, 1.03, 1.05, 1.02, .9, .82, 1.03, 1.06, 1.04, .9])[dd.month - 1]
    growth = 1 + 0.035 * (dd.year - 2022)
    run_h = np.clip(np.where(alive & ~shut, 20 * wk * seas * rng.normal(1, 0.08, L * D), 0), 0, 24)
    down = np.where(run_h > 0, np.clip(rng.gamma(1.2, 0.8, L * D), 0, 8), 0)
    out = run_h * lf.rated_capacity_units_per_hr.values[li] * lf.oee_baseline.values[li] * growth * rng.normal(1, 0.05, L * D)
    eff_impr = 1 - 0.022 * (dd.year - 2022)
    kwh = np.where(run_h > 0, (out * 9.5 * lf.energy_intensity_index.values[li] * eff_impr + 180 * lf.energy_intensity_index.values[li]) * rng.normal(1, 0.04, L * D), 25 * rng.random(L * D))
    mes = pd.DataFrame(dict(mes_record_id=ids("MESD-", L * D, 7), production_line_id=lf.production_line_id.values[li], facility_id=lf.facility_id.values[li], production_date=dd,
                            run_hours=np.round(run_h, 2), downtime_hours=np.round(down, 2), idle_hours=np.round(np.clip(24 - run_h - down, 0, 24), 2), output_units=np.round(out, 1),
                            defect_rate_pct=np.round(np.clip(rng.gamma(2, 0.6, L * D), 0, 15), 2), rework_units=np.round(out * rng.beta(1, 80, L * D), 1),
                            energy_kwh=np.round(kwh, 1), scrap_kg=np.round(out * rng.gamma(2, 0.4, L * D), 1), process_water_m3=np.round(out * 0.012 * rng.lognormal(0, 0.2, L * D), 2)))
    mes["oee_pct"] = np.round(100 * np.clip(mes.run_hours / 24 * (1 - mes.defect_rate_pct / 100) * lf.oee_baseline.values[li] / 0.75, 0, 1), 1)
    mes = mes[alive].reset_index(drop=True)
    sp = rng.choice(np.where(mes.run_hours.values > 0)[0], 900, replace=False)
    e = mes.energy_kwh.values[sp].copy(); mes.loc[sp, "energy_kwh"] = np.round(e * rng.uniform(2.2, 4.5, len(sp)), 1)
    lo = rng.choice(np.where(mes.run_hours.values > 0)[0], 700, replace=False)
    e2 = mes.oee_pct.values[lo].copy(); mes.loc[lo, "oee_pct"] = np.round(e2 * rng.uniform(0.2, 0.45, len(lo)), 1); mes.loc[lo, "downtime_hours"] = np.round(mes.downtime_hours.values[lo] + rng.uniform(8, 14, len(lo)), 1)
    ctx.lineage(mes, "MES", "SynthMES 7", "MESDB", "LINE_DAILY_KPI", "Operations", mes.mes_record_id.str.replace("MESD-", "LD").values)
    ctx.save(mes, "Manufacturing/MES/line_daily_performance.parquet", "mes_line_daily", pk="mes_record_id", fks={"production_line_id": "production_lines.production_line_id", "facility_id": "facilities.facility_id"}, system="MES")
    ctx.anom("mes_line_daily", mes.mes_record_id.values[sp], "Operational", "Unexplained production energy spikes", "High", e, mes.energy_kwh.values[sp], "Compressed-air leak / stuck heater",
             "Energy per unit z-score > 4 vs line baseline", "Inspect line; correct only if metering fault", process="Manufacturing", ghg="Scope 2", impact=(mes.energy_kwh.values[sp] - e) * 0.4, family="Operational_Anomalies")
    ctx.anom("mes_line_daily", mes.mes_record_id.values[lo], "Operational", "Low machine efficiency / unusual downtime", "Medium", e2, mes.oee_pct.values[lo], "Unplanned breakdown", "OEE drop vs rolling 28-day median",
             "Root-cause breakdown; maintenance", process="Manufacturing", family="Operational_Anomalies")
    # hourly machine records (sample month per year)
    ma = assets[assets.production_line_id.notna()].sample(100, random_state=ctx.seed)
    hrs = pd.date_range("2025-03-01", "2025-03-31 23:00", freq="h")
    mi = np.repeat(np.arange(100), len(hrs)); hi = np.tile(np.arange(len(hrs)), 100)
    hh = hrs[hi]
    on = (hh.dayofweek < 5) & (hh.hour >= 6) & (hh.hour < 22) | (rng.random(len(hh)) < 0.1)
    load = np.where(on, np.clip(rng.normal(0.72, 0.12, len(hh)), 0.1, 1), 0.03)
    mh = pd.DataFrame(dict(machine_id=ma.machine_id.values[mi], asset_id=ma.asset_id.values[mi], timestamp_utc=hh, status=np.where(on, "RUNNING", "IDLE"), load_pct=np.round(100 * load, 1),
                           power_kw=np.round(ma.rated_power_kw.values[mi] * load, 2), temperature_c=np.round(35 + 40 * load + rng.normal(0, 2, len(hh)), 1),
                           pressure_bar=np.round(6 + 2 * load + rng.normal(0, .2, len(hh)), 2), operating_hours_counter=np.round(np.cumsum(on.reshape(100, -1), axis=1).ravel() + 15000, 0)))
    ctx.save(mh, "Manufacturing/Machines/machine_hourly_2025-03.parquet", "machine_hourly", fks={"asset_id": "assets.asset_id"}, system="MES")
    # maintenance
    n_m = ctx.n(500000)
    ai = rng.choice(len(assets), n_m, p=(assets.rated_power_kw.values + 20) / (assets.rated_power_kw.values + 20).sum())
    a = assets.iloc[ai]
    mt = rng.choice(["Preventive", "Corrective", "Predictive", "Inspection", "Refrigerant service"], n_m, p=[.45, .25, .1, .15, .05])
    mt = np.where(a.refrigerant_charge_kg.values > 0, np.where(rng.random(n_m) < 0.45, "Refrigerant service", mt), np.where(mt == "Refrigerant service", "Inspection", mt))
    mdate = clip_active(rand_dates(rng, n_m), a.acquisition_date.values, a.retirement_date.values)
    top = np.where(mt == "Refrigerant service", np.round(a.refrigerant_charge_kg.values * rng.beta(1.5, 14, n_m), 2), 0.0)
    mr = pd.DataFrame(dict(maintenance_id=ids("MNT-", n_m, 7), cmms_wo=np.char.add("WO", rng.choice(10 ** 8, n_m, replace=False).astype(str)), asset_id=a.asset_id.values,
                           facility_id=a.facility_id.values, maintenance_type=mt, work_date=mdate, downtime_hours=np.round(np.where(mt == "Corrective", rng.gamma(2, 3, n_m), rng.gamma(1.2, 1, n_m)), 2),
                           labour_hours=np.round(rng.gamma(2, 2, n_m), 1), parts_cost_usd=np.round(rng.lognormal(5.5, 1.2, n_m), 2), refrigerant_type=np.where(top > 0, a.refrigerant_type.values, None),
                           refrigerant_added_kg=top, refrigerant_recovered_kg=np.where(top > 0, np.round(top * rng.uniform(0, 0.2, n_m), 2), 0.0), technician_contractor_id=None))
    lk = rng.choice(np.where(top > 0)[0], max(1, int((top > 0).sum() * 0.04)), replace=False)
    e = mr.refrigerant_added_kg.values[lk].copy(); mr.loc[lk, "refrigerant_added_kg"] = np.round(a.refrigerant_charge_kg.values[lk] * rng.uniform(0.45, 0.9, len(lk)), 2)
    ctx.lineage(mr, "CMMS", "SynthMaint", "CMMSDB", "WORK_ORDERS", "Maintenance", mr.cmms_wo.values, ts_col="work_date")
    ctx.save(mr, "Manufacturing/Maintenance/maintenance_records.parquet", "maintenance", pk="maintenance_id", fks={"asset_id": "assets.asset_id", "facility_id": "facilities.facility_id"}, target=500000, system="CMMS")
    ctx.anom("maintenance", mr.maintenance_id.values[lk], "Operational", "Refrigerant leakage", "High", e, mr.refrigerant_added_kg.values[lk], "Major leak in chiller circuit", "Top-up > 40% of nameplate charge",
             "Leak test & repair; report fugitive emissions", process="Facilities", ghg="Scope 1 Fugitive", family="Operational_Anomalies")
    qi = po.sample(frac=0.8, random_state=2)
    ctx.save(pd.DataFrame(dict(inspection_id=ids("QIN-", len(qi), 7), production_order_id=qi.production_order_id.values, inspection_date=qi.actual_finish.values,
                               sample_size=rng.integers(5, 200, len(qi)), defects_found=rng.poisson(1.2, len(qi)), result=rng.choice(["Pass", "Pass", "Pass", "Conditional", "Fail"], len(qi)),
                               qms_ref=np.char.add("QMS-NC-", rng.integers(10 ** 5, 10 ** 6, len(qi)).astype(str)))),
             "Manufacturing/Quality/quality_inspections.parquet", "quality_inspections", pk="inspection_id", fks={"production_order_id": "production_orders.production_order_id"}, system="QMS")
