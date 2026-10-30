import json, hashlib
import numpy as np
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from docx import Document
from openpyxl import Workbook
from .core import ids

BANNER = "SYNTHETIC DOCUMENT - generated test data - not a real business record"


def pdf(title, org, kv, header, rows, notes=(), pages=1, declared_pages=None):
    b = BytesIO(); c = canvas.Canvas(b, pagesize=A4); W, H = A4
    per = max(1, int(np.ceil(len(rows) / pages))) if rows else 1
    for p in range(pages):
        c.setFont("Helvetica-Bold", 14); c.drawString(40, H - 50, title[:80])
        c.setFont("Helvetica", 8); c.drawString(40, H - 64, org[:110]); c.setFillGray(0.5); c.drawString(40, 20, BANNER); c.setFillGray(0)
        c.drawRightString(W - 40, 20, f"Page {p + 1} of {declared_pages or pages}")
        y = H - 90
        if p == 0:
            for k, v in kv:
                c.setFont("Helvetica-Bold", 8); c.drawString(40, y, f"{k}:"); c.setFont("Helvetica", 8); c.drawString(190, y, str(v)[:80]); y -= 12
            y -= 8
        if header:
            c.setFont("Helvetica-Bold", 7); xs = np.linspace(40, W - 60, len(header) + 1)[:-1]
            for x, h in zip(xs, header): c.drawString(x, y, str(h)[:22])
            y -= 11; c.setFont("Helvetica", 7)
            for r in rows[p * per:(p + 1) * per]:
                for x, v in zip(xs, r): c.drawString(x, y, str(v)[:24])
                y -= 10
                if y < 60: break
        if p == pages - 1:
            for n in notes:
                y -= 12; c.setFont("Helvetica-Oblique", 7); c.drawString(40, max(y, 40), str(n)[:120])
        c.showPage()
    c.save(); return b.getvalue()


def docx(title, paras, header=None, rows=None):
    d = Document(); d.add_heading(title, 1); d.add_paragraph(BANNER)
    for p in paras:
        if isinstance(p, tuple): d.add_heading(p[1], 2)
        else: d.add_paragraph(p)
    if header:
        t = d.add_table(rows=1, cols=len(header)); t.style = "Table Grid"
        for i, h in enumerate(header): t.rows[0].cells[i].text = str(h)
        for r in rows[:60]:
            cells = t.add_row().cells
            for i, v in enumerate(r): cells[i].text = str(v)
    b = BytesIO(); d.save(b); return b.getvalue()


class Docs:
    def __init__(self, ctx):
        self.ctx, self.reg, self.ext, self.n = ctx, [], [], 0

    def add(self, dtype, fmt, folder, name, content, rel_ds=None, rel_id=None, fac=None, period=None, dept="Sustainability", system="DMS", title=None, extracted=None):
        self.n += 1
        did = f"DOC-{self.n:06d}"
        rel = f"File_Systems/Documents/{fmt.upper()}/{folder}/{did}_{name}.{fmt}"
        p = self.ctx.path(rel)
        p.write_bytes(content) if isinstance(content, bytes) else p.write_text(content)
        data = p.read_bytes()
        self.reg.append(dict(document_id=did, document_type=dtype, file_format=fmt, path=rel, filename=p.name, title=title or name.replace("_", " "), related_dataset=rel_ds, related_record_id=rel_id,
                             facility_id=fac, reporting_period=period, owner_department=dept, source_system=system, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), synthetic_flag=True))
        if extracted:
            for k, v in extracted.items():
                self.ext.append(dict(document_id=did, field_name=k, extracted_value=str(v), source_record_id=rel_id, source_dataset=rel_ds))
        return did


def gen_documents(ctx):
    rng = ctx.rng("docs")
    D = Docs(ctx)
    s = ctx.n_docs / 3000
    N = lambda k: max(1, int(k * s))
    ui, ap, po, pol = ctx.get("utility_invoices"), ctx.get("ap_invoices"), ctx.get("purchase_orders"), ctx.get("po_lines")
    sup = ctx.get("suppliers").set_index("supplier_id"); fac = ctx.get("facilities").set_index("facility_id")
    # utility invoices
    u = ui[ui.utility_type.isin(["electricity", "natural_gas", "water"])].sample(N(500), random_state=1)
    bad = set(rng.choice(len(u), int(len(u) * 0.06), replace=False)); miss = set(rng.choice(len(u), int(len(u) * 0.02), replace=False)); mis_t = set(rng.choice(len(u), int(len(u) * 0.01), replace=False))
    for i, r in enumerate(u.itertuples()):
        cons = r.consumption * (rng.choice([1.07, 0.9, 1.15]) if i in bad else 1)
        ttl = f"{'Natural Gas' if (i in mis_t and r.utility_type == 'electricity') else r.utility_type.replace('_', ' ').title()} Invoice {r.invoice_number}"
        kv = [("Utility supplier", sup.supplier_name.get(r.utility_supplier_id, r.utility_supplier_id)), ("Customer account", r.customer_account_no), ("Facility", f"{r.facility_id} {fac.facility_name.get(r.facility_id, '')}"),
              ("Meter", r.meter_id), ("Billing period", f"{pd.Timestamp(r.billing_period_start):%d %b %Y} - {pd.Timestamp(r.billing_period_end):%d %b %Y}"), ("Invoice date", f"{pd.Timestamp(r.invoice_date):%d/%m/%Y}"),
              ("Previous reading", f"{r.previous_reading:,.2f}"), ("Current reading", f"{r.previous_reading + cons:,.2f}"), ("Consumption", f"{cons:,.2f} {r.unit}"), ("Tariff", f"{r.tariff_per_unit} {r.currency}/{r.unit}")]
        rows = [["Energy charge", f"{cons * r.tariff_per_unit:,.2f}"], ["Network / distribution", f"{r.network_charge:,.2f}"], ["Taxes & levies", f"{r.taxes:,.2f}"], ["TOTAL PAYABLE", f"{cons * r.tariff_per_unit + r.network_charge + r.taxes:,.2f} {r.currency}"]]
        did = D.add("Utility invoice", "pdf", "Utility_Invoices", r.invoice_number, pdf(ttl, "Synthetic Utility Co. (FICTIONAL)", kv, ["Charge", "Amount"], rows, pages=1, declared_pages=(3 if i in miss else 1)),
                    "utility_invoices", r.utility_invoice_id, r.facility_id, str(pd.Timestamp(r.billing_period_start).to_period("M")), "Energy Management", "DMS", ttl,
                    dict(invoice_number=r.invoice_number, meter_id=r.meter_id, consumption=round(cons, 2), unit=r.unit, total_payable=round(cons * r.tariff_per_unit + r.network_charge + r.taxes, 2)))
        if i in bad:
            ctx.anom("documents", [did], "Document inconsistency", "Inconsistent PDF and ERP figures", "High", r.consumption, round(cons, 2), "Re-issued bill not re-captured in ERP", "Document extraction vs ERP reconciliation", "Request corrected invoice", related=r.utility_invoice_id, ghg="Scope 1/2", family="Document_Anomalies")
        if i in miss:
            ctx.anom("documents", [did], "Document completeness", "Missing invoice pages", "Medium", "3 pages", "1 page", "Scanner fed single page", "Page count vs 'Page x of y'", "Request full invoice", related=r.utility_invoice_id, family="Document_Anomalies")
        if i in mis_t:
            ctx.anom("documents", [did], "Document inconsistency", "Misleading document titles", "Low", r.utility_type, "Natural Gas", "Template reuse", "Title vs content classifier", "Reclassify document", related=r.utility_invoice_id, family="Document_Anomalies")
    # supplier invoices / POs / GRNs
    a = ap[ap.po_id.notna()].sample(N(400), random_state=2)
    wrongref = set(rng.choice(len(a), int(len(a) * 0.03), replace=False))
    pl = pol.set_index("po_id")
    for i, r in enumerate(a.itertuples()):
        lines = pl.loc[[r.po_id]] if r.po_id in pl.index else pd.DataFrame()
        ref = po.po_id.values[rng.integers(len(po))] if i in wrongref else r.po_id
        rows = [[l.material_id or l.service_category, l.order_qty, l.unit, l.unit_price, l.net_amount] for l in lines.itertuples()][:25]
        did = D.add("Supplier invoice", "pdf", "Supplier_Invoices", r.supplier_invoice_no, pdf(f"INVOICE {r.supplier_invoice_no}", f"{sup.supplier_name.get(r.supplier_id, 'UNKNOWN VENDOR')} (SYNTHETIC)",
                    [("Bill to", f"{r.legal_entity_id} / {r.facility_id}"), ("Invoice date", f"{pd.Timestamp(r.invoice_date):%Y-%m-%d}"), ("PO reference", ref), ("Payment terms", r.payment_terms),
                     ("Net amount", f"{r.net_amount:,.2f} {r.currency}"), ("Tax", f"{r.tax_amount:,.2f}"), ("Total", f"{r.gross_amount:,.2f} {r.currency}")], ["Item", "Qty", "Unit", "Price", "Net"], rows),
                    "ap_invoices", r.invoice_id, r.facility_id, str(pd.Timestamp(r.invoice_date).to_period("M")), "Finance", "DMS", None, dict(supplier_invoice_no=r.supplier_invoice_no, po_reference=ref, gross_amount=r.gross_amount))
        if i in wrongref:
            ctx.anom("documents", [did], "Document inconsistency", "Incorrect invoice references", "Medium", r.po_id, ref, "Supplier quoted wrong PO", "PO reference vs vendor/amount match", "Correct PO reference", related=r.invoice_id, family="Document_Anomalies")
    for r in po.sample(N(200), random_state=3).itertuples():
        lines = pl.loc[[r.po_id]] if r.po_id in pl.index else pd.DataFrame()
        D.add("Purchase order", "pdf", "Purchase_Orders", r.sap_ebeln, pdf(f"PURCHASE ORDER {r.sap_ebeln}", "Halvorsen-Kaito Industrial Holdings (SYNTHETIC)", [("Supplier", r.supplier_id), ("Date", f"{pd.Timestamp(r.po_date):%Y-%m-%d}"), ("Ship to", r.facility_id), ("Incoterm", r.incoterm), ("Total net", f"{r.total_net_amount:,.2f} {r.currency}")],
              ["Line", "Material", "Qty", "Unit", "Price"], [[l.line_no, l.material_id or l.service_category, l.order_qty, l.unit, l.unit_price] for l in lines.itertuples()]), "purchase_orders", r.po_id, r.facility_id, None, "Procurement", "SAP_S4")
    grn = ctx.get("goods_receipts").sample(N(100), random_state=4)
    for r in grn.itertuples():
        D.add("Goods receipt note", "pdf", "Goods_Receipts", r.sap_mblnr, pdf(f"GOODS RECEIPT NOTE {r.sap_mblnr}", "Warehouse Operations (SYNTHETIC)", [("PO line", r.po_line_id), ("Material", r.material_id), ("Received", f"{r.received_qty} {r.unit}"), ("Rejected", r.rejected_qty), ("Receipt date", f"{r.receipt_date:%d.%m.%Y}")], None, []),
              "goods_receipts", r.grn_id, r.facility_id, None, "Operations", "SAP_S4")
    fi_ = ctx.get("freight_invoices").sample(N(150), random_state=5)
    for r in fi_.itertuples():
        D.add("Freight invoice", "pdf", "Freight_Invoices", r.freight_invoice_id, pdf(f"FREIGHT INVOICE {r.freight_invoice_id}", f"{sup.supplier_name.get(r.carrier_id, r.carrier_id)}", [("Shipment", r.shipment_id), ("Mode", r.mode), ("Distance", f"{r.billed_distance_km} km"), ("Weight", f"{r.billed_weight_kg} kg"), ("Amount", f"USD {r.amount_usd:,.2f}")], None, []),
              "freight_invoices", r.freight_invoice_id, None, None, "Logistics", "TMS")
    ar = ctx.get("ar_invoices").sample(N(150), random_state=6)
    for r in ar.itertuples():
        D.add("Customer invoice", "pdf", "Customer_Invoices", r.sap_vbrk, pdf(f"INVOICE {r.sap_vbrk}", "Halvorsen-Kaito Industrial Holdings (SYNTHETIC)", [("Customer", r.customer_id), ("Delivery", r.delivery_id), ("Date", f"{pd.Timestamp(r.invoice_date):%Y-%m-%d}"), ("Total", f"{r.gross_amount:,.2f} {r.currency}")], None, []),
              "ar_invoices", r.ar_invoice_id, None, None, "Finance", "SAP_S4")
    wc = ctx.get("waste_certificates").sample(N(150), random_state=7)
    for r in wc.itertuples():
        D.add("Waste disposal certificate", "pdf", "Waste_Certificates", r.waste_certificate_id, pdf("CERTIFICATE OF DISPOSAL / RECOVERY", "Synthetic Waste Services Ltd (FICTIONAL)", [("Certificate", r.waste_certificate_id), ("Facility", r.facility_id), ("Waste type", r.waste_type), ("Quantity", f"{r.quantity} t"), ("Method", r.disposal_method), ("Period", r.period)], None, []),
              "waste_certificates", r.waste_certificate_id, r.facility_id, r.period, "EHS & Sustainability", "EHS")
    ins = ctx.get("contractual_instruments").head(N(80))
    for r in ins.itertuples():
        D.add("Renewable energy certificate", "pdf", "Energy_Attribute_Certificates", r.instrument_id, pdf(f"{r.instrument_type.upper()} - REDEMPTION STATEMENT", f"{r.registry}", [("Serial", r.serial_number), ("Vintage", r.vintage_year), ("Technology", r.technology), ("MWh", r.mwh), ("Market", r.market_boundary), ("Beneficiary", r.retired_on_behalf_of), ("Allocated to", r.allocated_facility_id)], None, []),
              "contractual_instruments", r.instrument_id, r.allocated_facility_id, str(r.allocation_year), "Energy Management", "EAC_REGISTRY")
    cc = ctx.get("credit_transactions").head(N(60))
    for r in cc.itertuples():
        D.add("Carbon credit retirement statement", "pdf", "Carbon_Credits", r.credit_transaction_id, pdf("CARBON CREDIT RETIREMENT STATEMENT", "Synthetic Registry (FICTIONAL)", [("Project", r.project_id), ("Serial block", r.serial_number_block), ("Vintage", r.vintage_year), ("Credits retired", r.credits_retired), ("Class", r.credit_class), ("Retired on", f"{r.retirement_date:%Y-%m-%d}"), ("Certificate", r.retirement_certificate_ref)], None, []),
              "credit_transactions", r.credit_transaction_id, None, str(r.purchase_year), "EHS & Sustainability", "CARBON_REGISTRY")
    pc = ctx.get("supplier_pcfs").sample(N(80), random_state=8)
    for r in pc.itertuples():
        D.add("Supplier PCF report", "pdf", "Supplier_PCF", r.pcf_id, pdf("PRODUCT CARBON FOOTPRINT DECLARATION", f"{sup.supplier_name.get(r.supplier_id, r.supplier_id)}", [("Material", r.material_family), ("PCF", f"{r.declared_kgco2e_per_unit} kgCO2e/{r.declared_unit}"), ("Boundary", r.system_boundary), ("Standard", r.standard), ("Reference year", r.reference_year), ("Verification", r.verification), ("Primary data share", f"{r.primary_data_share_pct}%")], None, [], notes=["Uncertainty +/-15% (synthetic)"]),
              "supplier_pcfs", r.pcf_id, None, str(r.reference_year), "Procurement", "SUPPLIER_PORTAL")
    pm = ctx.get("environmental_permits").head(N(50))
    for r in pm.itertuples():
        D.add("Environmental permit", "pdf", "Permits", r.permit_id, pdf(f"ENVIRONMENTAL PERMIT {r.permit_id}", r.issuing_authority, [("Facility", r.facility_id), ("Type", r.permit_type), ("Issued", f"{r.issue_date:%Y-%m-%d}"), ("Expires", f"{r.expiry_date:%Y-%m-%d}")], None, []),
              "environmental_permits", r.permit_id, r.facility_id, None, "EHS & Sustainability", "EHS")
    # DOCX
    mt = ctx.get("maintenance"); rf = mt[mt.maintenance_type == "Refrigerant service"].sample(N(120), random_state=9)
    for r in rf.itertuples():
        D.add("Refrigerant servicing report", "docx", "Refrigerant_Reports", r.cmms_wo, docx(f"F-Gas Service Report {r.cmms_wo}", [f"Asset {r.asset_id} at {r.facility_id} serviced on {r.work_date:%d %B %Y}.", f"Refrigerant {r.refrigerant_type}: {r.refrigerant_added_kg} kg added, {r.refrigerant_recovered_kg} kg recovered.", "Leak test performed with electronic detector (synthetic)."]),
              "maintenance", r.maintenance_id, r.facility_id, str(r.work_date.to_period("M")), "Maintenance", "CMMS", None, dict(refrigerant_type=r.refrigerant_type, added_kg=r.refrigerant_added_kg))
    fe = ctx.get("facility_emissions"); dec = ctx.get("decarbonisation")
    for fid in dec.facility_id.unique()[:N(40)]:
        o = dec[(dec.facility_id == fid) & (dec.scenario == "Base")]
        D.add("Energy audit report", "docx", "Energy_Audits", f"EA_{fid}", docx(f"Energy Audit Report - {fid}", [("h", "1. Scope"), "ISO 50002-style audit (synthetic) covering electricity, gas and compressed air.", ("h", "2. Findings"), f"{len(o)} opportunities identified."],
              ["Opportunity", "Baseline t", "Reduction t", "Capex USD", "Payback y"], [[x.opportunity_name, x.baseline_emissions_tco2e, x.interaction_adjusted_reduction_tco2e, x.implementation_cost_usd, x.payback_years] for x in o.itertuples()]), "decarbonisation", f"DOC-EA-{fid}", fid, "2024", "Energy Management", "DMS")
    ao = ctx.get("audit_observations").head(N(80))
    for r in ao.itertuples():
        D.add("Internal audit observation", "docx", "Audit", r.audit_observation_id, docx(f"{r.audit_type} - Observation {r.audit_observation_id}", [f"Finding: {r.finding}", f"Rating: {r.rating}. Responsible: {r.responsible_department}.", f"Corrective action due {r.corrective_action_due:%Y-%m-%d}. Status: {r.closure_status}."]),
              "audit_observations", r.audit_observation_id, r.facility_id, None, "Internal Audit", "GRC")
    ei = ctx.get("environmental_incidents").head(N(40))
    for r in ei.itertuples():
        D.add("Environmental incident report", "docx", "Incidents", r.incident_id, docx(f"Environmental Incident Report {r.incident_id}", [f"{r.incident_type} at {r.facility_id} on {r.incident_date:%Y-%m-%d}. Severity: {r.severity}.", f"Regulator notified: {r.reported_to_regulator}. CAPA {r.corrective_action_id}."]),
              "environmental_incidents", r.incident_id, r.facility_id, None, "EHS & Sustainability", "EHS")
    inv = ctx.get("ghg_inventory"); led = ctx.get("neutralisation_ledger").set_index("reporting_year")
    for y in range(2022, 2027):
        t = inv[inv.reporting_year == y]
        s1 = t[t.scope == "Scope 1"].tco2e.sum(); s3 = t[t.scope == "Scope 3"].tco2e.sum()
        rep_s1 = s1 * (0.93 if y == 2025 else 1)
        did = D.add("Corporate ESG report", "docx", "ESG_Reports", f"ESG_Report_{y}", docx(f"Sustainability Report {y} (SYNTHETIC)", [("h", "Climate"), f"Scope 1 emissions: {rep_s1:,.0f} tCO2e. Scope 3 emissions: {s3:,.0f} tCO2e.",
              ("Our operations were carbon neutral in 2025." if y == 2025 else "We continue to reduce absolute emissions against our 2022 baseline."), f"Carbon credits retired: {led.credits_retired_t.get(y, 0):,} t (not deducted from inventory)."],
              ["Scope", "Category", "tCO2e"], [[r.scope, r.category_id, r.tco2e] for r in t.itertuples()]), "ghg_inventory", str(y), None, str(y), "Corporate Reporting", "DMS")
        if y == 2025:
            ctx.anom("documents", [did], "Reporting", "Unsupported calculations (report figure differs from inventory)", "High", round(s1, 0), round(rep_s1, 0), "Report drafted from preliminary data", "Report vs inventory reconciliation", "Restate report figure", ghg="Scope 1", family="Governance_Anomalies")
        if y == 2022:
            ctx.anom("documents", [did], "Reporting", "Outdated sustainability reports", "Low", "current-year report", "2022 report still published as current", "Website not updated", "Document date check", "Archive", family="Document_Anomalies")
    D.add("Decarbonisation plan", "docx", "Decarbonisation", "Group_Decarbonisation_Plan_2025", docx("Group Decarbonisation Plan 2025-2030 (SYNTHETIC)", ["Hierarchy: avoid, reduce, substitute, then neutralise residual emissions with high-quality removals only.", f"{len(dec)} scenario rows evaluated across {dec.facility_id.nunique()} facilities."]), "decarbonisation", None, None, "2025", "EHS & Sustainability", "DMS")
    # XLSX workbooks with formulas
    ga = ctx.get("ghg_activities")
    fy = ga[(ga.scope != "Scope 3") & ga.included_in_inventory].groupby(["facility_id", "reporting_year"])
    keys = list(fy.groups.keys()); sel = [keys[i] for i in rng.choice(len(keys), min(N(150), len(keys)), replace=False)]
    for j, (fid, y) in enumerate(sel):
        g = fy.get_group((fid, y)).groupby(["scope", "category_id", "activity_type", "activity_unit", "emission_factor_id", "emission_factor_value"]).activity_quantity.sum().reset_index().head(40)
        wb = Workbook(); ws = wb.active; ws.title = "Calculation"
        ws.append([f"Carbon accounting workbook - {fid} - {y} (SYNTHETIC)"]); ws.append(["Scope", "Category", "Activity", "Unit", "Quantity", "EF ID", "EF kgCO2e/unit", "kgCO2e", "Reference"])
        badf = j % 20 == 0
        for i, r in enumerate(g.itertuples(), start=3):
            ws.append([r.scope, r.category_id, r.activity_type, r.activity_unit, round(r.activity_quantity, 3), r.emission_factor_id, r.emission_factor_value, f"=E{i}*G{i}" if not (badf and i == 3) else f"=E{i}*G{i}/1000", "ERP/EMS extract"])
        ws.append(["TOTAL", "", "", "", "", "", "", f"=SUM(H3:H{len(g) + 2})"])
        b = BytesIO(); wb.save(b)
        did = D.add("Carbon accounting workbook", "xlsx", "Carbon_Workbooks", f"GHG_{fid}_{y}", b.getvalue(), "facility_emissions", f"{fid}-{y}", fid, str(y), "EHS & Sustainability", "MANUAL")
        if badf:
            ctx.anom("documents", [did], "Spreadsheet", "Incorrect spreadsheet formulas", "High", "=E3*G3", "=E3*G3/1000", "Analyst unit-conversion slip", "Formula pattern audit", "Fix formula", ghg="Scope 1/2", family="Document_Anomalies")
    mes = ctx.get("mes_line_daily")
    for r in mes.sample(N(150), random_state=10).itertuples():
        wb = Workbook(); ws = wb.active
        ws.append(["Daily production report (SYNTHETIC)", r.production_line_id, str(r.production_date.date())])
        for k in ["run_hours", "downtime_hours", "output_units", "defect_rate_pct", "energy_kwh", "scrap_kg", "oee_pct"]:
            ws.append([k, getattr(r, k)])
        ws.append(["energy_per_unit_kwh", "=B7/MAX(B5,1)"])
        b = BytesIO(); wb.save(b)
        D.add("Daily production report", "xlsx", "Production_Reports", f"DPR_{r.production_line_id}_{r.production_date:%Y%m%d}", b.getvalue(), "mes_line_daily", r.mes_record_id, r.facility_id, str(r.production_date.to_period("M")), "Operations", "MES")
    sq = ctx.get("supplier_questionnaires").head(N(100))
    for r in sq.itertuples():
        wb = Workbook(); ws = wb.active; ws.append(["Supplier ESG questionnaire (SYNTHETIC)", r.supplier_id])
        for k in ["q_has_climate_policy", "q_scope1_disclosed", "q_renewable_pct", "q_iso14001", "q_child_labour_policy", "q_material_origin_country"]:
            v = getattr(r, k); ws.append([k, None if (v is None or (isinstance(v, float) and np.isnan(v))) else v])
        b = BytesIO(); wb.save(b)
        D.add("Supplier sustainability questionnaire", "xlsx", "Supplier_Questionnaires", r.questionnaire_id, b.getvalue(), "supplier_questionnaires", r.questionnaire_id, None, None, "Procurement", "SUPPLIER_PORTAL")
    bt = ctx.get("business_travel")
    for k, (rid, g) in enumerate(bt.head(N(80) * 3).groupby("expense_report_id")):
        if k >= N(80): break
        wb = Workbook(); ws = wb.active; ws.append(["Trip", "Date", "Mode", "Distance km", "Hotel nights", "Cost USD"])
        for r in g.itertuples(): ws.append([r.trip_id, str(r.travel_date.date()), r.travel_mode, r.distance_km, r.hotel_nights, r.cost_usd])
        ws.append(["TOTAL", "", "", "", "", f"=SUM(F2:F{len(g) + 1})"])
        b = BytesIO(); wb.save(b)
        D.add("Expense report", "xlsx", "Expense_Reports", rid, b.getvalue(), "business_travel", g.trip_id.iloc[0], None, None, "Finance", "CONCUR_LIKE")
    for y in range(2022, 2027):
        b = BytesIO(); inv[inv.reporting_year == y].to_excel(b, index=False)
        D.add("GHG inventory", "xlsx", "GHG_Inventories", f"GHG_Inventory_{y}", b.getvalue(), "ghg_inventory", str(y), None, str(y), "Corporate Reporting", "GHG_PLATFORM")
    # EML
    sd = ctx.get("supplier_disclosures").sample(N(150), random_state=11)
    for r in sd.itertuples():
        D.add("Email", "eml", "Supplier_Correspondence", r.disclosure_id, f"From: sustainability@{r.supplier_id.lower()}.synthetic-supplier.example\nTo: supplier-esg@hkih.synthetic.example\nSubject: {r.reporting_year} emissions disclosure - {r.supplier_id}\nDate: {r.submission_date:%a, %d %b %Y 10:12:00 +0000}\nMIME-Version: 1.0\nContent-Type: text/plain; charset=utf-8\nX-Synthetic: true\n\nDear team,\n\nPlease find our {r.reporting_period} disclosure: Scope 1 {r.scope1_tco2e} {r.reported_unit}, Scope 2 {r.scope2_tco2e} tCO2e, methodology {r.methodology}, verification: {r.verification_status}.\nRenewable electricity: {r.renewable_electricity_pct}%.\n\nRegards,\nSupplier sustainability desk (synthetic)\n",
              "supplier_disclosures", r.disclosure_id, None, str(r.reporting_year), "Procurement", "EXCHANGE")
    for r in u.head(N(150)).itertuples():
        D.add("Email", "eml", "Utility_Correspondence", r.invoice_number, f"From: billing@synthetic-utility.example\nTo: ap-energy@hkih.synthetic.example\nSubject: Your bill {r.invoice_number} for account {r.customer_account_no}\nDate: {pd.Timestamp(r.invoice_date):%a, %d %b %Y 07:00:00 +0000}\nX-Synthetic: true\n\nYour {r.utility_type} bill for {pd.Timestamp(r.billing_period_start):%B %Y} is attached (PDF). Amount due: {r.total_payable:,.2f} {r.currency}.\n",
              "utility_invoices", r.utility_invoice_id, r.facility_id, None, "Finance", "EXCHANGE")
    # TXT OCR, maintenance, MD, LOG, CSV/JSON/XML/DAT
    def ocr(t):
        t = list(t)
        for i in rng.choice(len(t), max(1, len(t) // 40), replace=False):
            t[i] = {"0": "O", "1": "l", "5": "S", "8": "B", ".": ",", "e": "c"}.get(t[i], t[i])
        return "".join(t)
    for r in u.tail(N(120)).itertuples():
        txt = f"INVOICE NO {r.invoice_number}\nACCOUNT {r.customer_account_no}\nMETER {r.meter_id}\nPERIOD {pd.Timestamp(r.billing_period_start):%d/%m/%Y} TO {pd.Timestamp(r.billing_period_end):%d/%m/%Y}\nCONSUMPTION {r.consumption:.2f} {r.unit}\nTOTAL {r.total_payable:.2f} {r.currency}\n"
        did = D.add("OCR text", "txt", "OCR_Scans", f"OCR_{r.invoice_number}", ocr(txt), "utility_invoices", r.utility_invoice_id, r.facility_id, None, "Finance", "OCR_ENGINE")
        ctx.anom("documents", [did], "OCR", "OCR extraction errors", "Low", f"{r.consumption:.2f}", "character substitutions", "Low-resolution scan", "Checksum / regex validation", "Re-scan or manual verification", related=r.utility_invoice_id, family="Document_Anomalies")
    for r in mt.sample(N(80), random_state=12).itertuples():
        D.add("Maintenance report", "txt", "Maintenance_Reports", r.cmms_wo, f"WORK ORDER {r.cmms_wo}\nASSET {r.asset_id}\nTYPE {r.maintenance_type}\nDATE {r.work_date:%m/%d/%Y}\nDOWNTIME_H {r.downtime_hours}\nLABOUR_H {r.labour_hours}\nPARTS_USD {r.parts_cost_usd}\n-- SYNTHETIC --\n", "maintenance", r.maintenance_id, r.facility_id, None, "Maintenance", "CMMS")
    for r in ctx.get("esg_policies").itertuples():
        D.add("ESG policy", "md", "Policies", r.policy_id, f"# {r.title}\n\n> {BANNER}\n\n- Version: {r.version}\n- Approved: {r.approved_date}\n- Owner: {r.owner}\n\n## Commitments\n\n1. Follow the mitigation hierarchy: avoid, reduce, substitute, neutralise residual only.\n2. Carbon credits never reported as inventory reductions.\n", "esg_policies", r.policy_id, None, None, "Legal & Compliance", "DMS")
    for fid, g in fe.groupby("facility_id"):
        if D.n > ctx.n_docs * 1.2: break
        D.add("Environmental performance report", "md", "Environmental_Reports", f"ENV_{fid}", f"# Environmental performance - {fid}\n\n> {BANNER}\n\n| Year | Scope | tCO2e |\n|---|---|---|\n" + "\n".join(f"| {r.reporting_year} | {r.scope} | {r.tco2e:,.1f} |" for r in g.itertuples()), "facility_emissions", fid, fid, None, "EHS & Sustainability", "DMS")
    iot = ctx.get("iot_telemetry")
    for sid, g in list(iot.groupby("sensor_id"))[:N(30)]:
        D.add("Process monitoring log", "log", "Process_Logs", sid, "\n".join(f"{r.timestamp_utc} {sid} {r.measurement_type}={r.value} {r.unit} status={r.device_status} comm={r.comm_status}" for r in g.head(400).itertuples()), "iot_telemetry", sid, g.facility_id.iloc[0], "2025-11", "Operations", "SCADA")
    pay = ctx.get("ap_payments")
    for k, (sid, g) in enumerate(pay.head(5000).groupby("supplier_id")):
        if k >= N(50): break
        D.add("Payment statement", "csv", "Payment_Statements", f"PAYSTMT_{sid}", g.to_csv(index=False), "ap_payments", g.payment_id.iloc[0], None, None, "Finance", "BANK")
    for r in ap.head(N(50)).itertuples():
        D.add("E-invoice", "json", "E_Invoices", r.invoice_id, json.dumps(dict(invoice=r.supplier_invoice_no, seller=r.supplier_id, buyer=r.legal_entity_id, po=r.po_id, net=r.net_amount, tax=r.tax_amount, currency=r.currency, synthetic=True), default=str), "ap_invoices", r.invoice_id, r.facility_id, None, "Finance", "EINVOICE")
        D.add("E-invoice", "xml", "E_Invoices", r.invoice_id, f'<?xml version="1.0"?><Invoice synthetic="true"><ID>{r.supplier_invoice_no}</ID><Seller>{r.supplier_id}</Seller><Total currency="{r.currency}">{r.gross_amount}</Total><OrderReference>{r.po_id}</OrderReference></Invoice>', "ap_invoices", r.invoice_id, r.facility_id, None, "Finance", "EINVOICE")
    for r in ctx.get("fuel_purchases").head(N(20)).itertuples():
        D.add("Fuel delivery note", "dat", "Fuel_Delivery", r.fuel_purchase_id, f"{r.fuel_purchase_id:<12}{r.facility_id:<12}{r.fuel_type:<10}{r.quantity:>14.3f}{r.unit:<4}{r.delivery_date:%Y%m%d}", "fuel_purchases", r.fuel_purchase_id, r.facility_id, r.period, "Energy Management", "LEGACY_FUEL")
    # duplicate documents
    reg = pd.DataFrame(D.reg)
    dsrc = reg[reg.file_format == "pdf"].sample(min(30, len(reg)), random_state=13)
    for r in dsrc.itertuples():
        did = D.add(r.document_type, "pdf", "Scans_Inbox", "copy_" + r.filename.split("_", 1)[1].rsplit(".", 1)[0], ctx.path(r.path).read_bytes(), r.related_dataset, r.related_record_id, r.facility_id, r.reporting_period, r.owner_department, "SHAREPOINT_LIKE")
        ctx.anom("documents", [did], "Duplicate record", "Duplicate documents", "Low", "single document", r.document_id, "Same file uploaded to inbox and archive", "File hash match", "Deduplicate", related=r.document_id, family="Document_Anomalies")
    reg = pd.DataFrame(D.reg)
    reg["created_date"] = pd.Timestamp.now(tz="UTC").floor("s"); reg["modified_date"] = reg.created_date
    ctx.save(reg, "File_Systems/document_registry.csv", "documents", pk="document_id", system="DMS", domain="File_Systems")
    ctx.save(pd.DataFrame(D.ext).assign(extraction_id=lambda d: ids("EXT-", len(d), 7)), "Data_Lineage/document_extractions.csv", "document_extractions", pk="extraction_id", fks={"document_id": "documents.document_id"}, system="IDP_ENGINE")
