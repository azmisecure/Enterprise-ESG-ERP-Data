import json
import numpy as np
import pandas as pd
from .core import ids, MONTHS, END

DIALECT = {"PostgreSQL": {"object": "TEXT", "int64": "BIGINT", "float64": "NUMERIC(20,6)", "bool": "BOOLEAN", "datetime": "TIMESTAMP"},
           "SQL_Server": {"object": "NVARCHAR(255)", "int64": "BIGINT", "float64": "DECIMAL(20,6)", "bool": "BIT", "datetime": "DATETIME2"},
           "Oracle": {"object": "VARCHAR2(255)", "int64": "NUMBER(19)", "float64": "NUMBER(20,6)", "bool": "NUMBER(1)", "datetime": "TIMESTAMP"},
           "MySQL": {"object": "VARCHAR(255)", "int64": "BIGINT", "float64": "DECIMAL(20,6)", "bool": "TINYINT(1)", "datetime": "DATETIME"}}


def sqlt(d, dt):
    k = "datetime" if dt.startswith("datetime") else dt if dt in ("int64", "float64", "bool") else "object"
    return DIALECT[d][k]


def lit(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NaT:
        return "NULL"
    if isinstance(v, (bool, np.bool_)):
        return "1" if v else "0"
    if isinstance(v, (int, float, np.integer, np.floating)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def gen_legacy(ctx):
    rng = ctx.rng("legacy")
    ap, gl, fac = ctx.get("ap_invoices"), ctx.get("gl_transactions"), ctx.get("facilities")
    # inventory balances & stock movements (ERP inventory)
    grn, mc = ctx.get("goods_receipts"), ctx.get("material_consumption")
    rc = grn[grn.material_id.notna()].assign(period=lambda d: d.receipt_date.dt.to_period("M").astype(str)).groupby(["facility_id", "material_id", "period"]).accepted_qty.sum().rename("receipts")
    cs = mc.assign(period=lambda d: pd.to_datetime(d.posting_date).dt.to_period("M").astype(str)).groupby(["facility_id", "material_id", "period"]).consumed_qty.sum().rename("issues")
    ib = pd.concat([rc, cs], axis=1).fillna(0).reset_index().sort_values(["facility_id", "material_id", "period"])
    ib["opening_stock"] = 0.0
    ib["closing_stock"] = (ib.groupby(["facility_id", "material_id"]).receipts.cumsum() - ib.groupby(["facility_id", "material_id"]).issues.cumsum() * 0.35).round(3)
    ib["valuation_usd"] = (ib.closing_stock.clip(lower=0) * ib.material_id.map(ctx.get("materials").set_index("material_id").standard_price_usd)).round(2)
    ib["stock_status"] = np.where(ib.closing_stock < 0, "Negative (posting lag)", "OK")
    ctx.save(ib, "ERP/Inventory/inventory_balances_monthly.parquet", "inventory_balances", fks={"material_id": "materials.material_id", "facility_id": "facilities.facility_id"}, system="SAP_S4")
    nt = 6000
    whs = fac[fac.facility_type == "Warehouse/DC"].facility_id.values
    tr = pd.DataFrame(dict(transfer_id=ids("WTR-", nt, 6), from_facility_id=rng.choice(whs, nt), to_facility_id=rng.choice(whs, nt), material_id=ctx.get("materials").material_id.values[rng.integers(0, 5000, nt)],
                           qty=np.round(rng.lognormal(5, 1, nt), 2), movement_type="311", posting_date=pd.to_datetime(rng.choice(pd.date_range("2022-01-03", "2026-12-28"), nt))))
    ctx.save(tr, "ERP/Inventory/warehouse_transfers.parquet", "warehouse_transfers", pk="transfer_id", system="SAP_S4")
    # mainframe fixed-width AP 2022 + copybook
    a = ap[pd.to_datetime(ap.invoice_date).dt.year == 2022].head(4000)
    lines = [f"{r.invoice_id:<14}{str(r.supplier_id or ''):<10}{pd.Timestamp(r.invoice_date):%Y%m%d}{int(round(abs(r.net_amount) * 100)):013d}{'-' if r.net_amount < 0 else '+'}{r.currency:<3}{str(r.po_id or ''):<12}{r.legal_entity_id or '':<8}"
             for r in a.itertuples()]
    ctx.write("Traditional_IT/Mainframe/APINV_2022.DAT", "\n".join(lines), kind="legacy", system="MAINFRAME_AP", dept="Finance", period="2022")
    ctx.write("Traditional_IT/Mainframe/APINV.cpy", """      * SYNTHETIC COPYBOOK - AP INVOICE EXTRACT (MAINFRAME AP v2.3)
       01  AP-INVOICE-REC.
           05  INV-ID          PIC X(14).
           05  VENDOR-ID       PIC X(10).
           05  INV-DATE        PIC 9(8).     *> CCYYMMDD
           05  NET-AMT         PIC 9(11)V99. *> IMPLIED DECIMAL
           05  NET-SIGN        PIC X.
           05  CURRENCY        PIC X(3).
           05  PO-REF          PIC X(12).
           05  ENTITY          PIC X(8).
""", kind="legacy", system="MAINFRAME_AP")
    ctx.write("Traditional_IT/Mainframe/APINV_2022_SAMPLE.EBCDIC.DAT", "\n".join(lines[:200]).encode("cp037"), kind="legacy", system="MAINFRAME_AP")
    # legacy ERP pipe export (old field names, DD.MM.YYYY, comma decimals)
    g = gl[gl.posting_date.dt.year == 2022].head(20000)
    le = pd.DataFrame(dict(BELNR=g.journal_entry_id, BUZEI=g.line_no, BUKRS=g.company_code, HKONT=g.gl_account, BUDAT=g.posting_date.dt.strftime("%d.%m.%Y"),
                           SHKZG=np.where(g.debit_amount > 0, "S", "H"), WRBTR=(g.debit_amount + g.credit_amount).map(lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")),
                           WAERS=g.currency, KOSTL=g.cost_centre_id, SGTXT=g.transaction_description.str[:40]))
    ctx.write("Traditional_IT/Legacy_ERP/ECC_GL_EXPORT_2022.txt", le.to_csv(sep="|", index=False), kind="legacy", system="SAP_ECC_LEGACY", dept="Finance", period="2022")
    ctx.write("Traditional_IT/Legacy_ERP/ECC_GL_EXPORT_2022_noheader.txt", le.head(3000).to_csv(sep="|", index=False, header=False), kind="legacy", system="SAP_ECC_LEGACY")
    inv = ctx.get("inventory_balances").head(15000)
    eu = inv.assign(closing_stock=inv.closing_stock.map(lambda v: f"{v:.3f}".replace(".", ",")), Werk_Bezeichnung="Werk Düsseldorf-Süd (synthetisch)")
    ctx.write("Traditional_IT/Flat_Files/LAGERBESTAND_semicolon_latin1.csv", eu.to_csv(sep=";", index=False), kind="legacy", system="LEGACY_INVENTORY", encoding="latin-1")
    ctx.write("Traditional_IT/Flat_Files/WMS_TRANSFERS.tsv", tr.to_csv(sep="\t", index=False), kind="legacy", system="WMS")
    # EDI X12 850/810
    po, pol = ctx.get("purchase_orders"), ctx.get("po_lines")
    sp = po.head(300)
    pl = pol[pol.po_id.isin(sp.po_id)].groupby("po_id")
    edi850, edi810 = [], []
    for i, r in enumerate(sp.itertuples()):
        seg = [f"ISA*00*          *00*          *ZZ*HKIH-SYN       *ZZ*{r.supplier_id:<15}*{pd.Timestamp(r.po_date):%y%m%d}*1200*U*00401*{i:09d}*0*P*>~",
               f"GS*PO*HKIH*{r.supplier_id}*{pd.Timestamp(r.po_date):%Y%m%d}*1200*{i}*X*004010~", f"ST*850*{i:04d}~", f"BEG*00*SA*{r.sap_ebeln}**{pd.Timestamp(r.po_date):%Y%m%d}~"]
        lines_ = pl.get_group(r.po_id) if r.po_id in pl.groups else []
        for j, l in enumerate(getattr(lines_, "itertuples", lambda: [])()):
            seg.append(f"PO1*{j + 1}*{l.order_qty}*{l.unit}*{l.unit_price}**VP*{l.material_id or 'SERVICE'}~")
        seg += [f"CTT*{len(seg) - 4}~", f"SE*{len(seg) + 1}*{i:04d}~", f"GE*1*{i}~", f"IEA*1*{i:09d}~"]
        edi850.append("\n".join(seg))
    ctx.write("Traditional_IT/EDI/X12_850_purchase_orders.edi", "\n".join(edi850), kind="legacy", system="EDI_GATEWAY", dept="Procurement")
    for i, r in enumerate(ap[ap.po_id.notna()].head(300).itertuples()):
        edi810.append("\n".join([f"ST*810*{i:04d}~", f"BIG*{pd.Timestamp(r.invoice_date):%Y%m%d}*{r.supplier_invoice_no}**{r.po_id}~", f"N1*RE*{r.supplier_id}~", f"TDS*{int(round(r.gross_amount * 100))}~", f"CUR*SE*{r.currency}~", f"SE*6*{i:04d}~"]))
    ctx.write("Traditional_IT/EDI/X12_810_invoices.edi", "\n".join(edi810), kind="legacy", system="EDI_GATEWAY", dept="Finance")
    sh = ctx.get("shipments").head(3000)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<TMSExport system="SynthTMS" schemaVersion="2.1" synthetic="true">']
    for r in sh.itertuples():
        xml.append(f'  <Shipment id="{r.tms_ref}" canonical="{r.shipment_id}"><Mode>{r.mode}</Mode><Origin>{r.origin}</Origin><Destination>{r.destination}</Destination><ShipDate>{pd.Timestamp(r.ship_date):%Y-%m-%d}</ShipDate><Weight unit="kg">{r.weight_kg:.1f}</Weight><Distance unit="{r.distance_unit}">{r.distance_km}</Distance><Carrier>{r.carrier_id}</Carrier></Shipment>')
    xml.append("</TMSExport>")
    ctx.write("Traditional_IT/Batch_Exports/TMS_SHIPMENTS_EXPORT.xml", "\n".join(xml), kind="legacy", system="TMS")
    ui = ctx.get("utility_invoices")
    rep = []
    for fid, grp in ui[(ui.utility_type == "electricity")].groupby("facility_id"):
        g2 = grp.sort_values("billing_period_start").tail(12)
        rep.append(f"{'=' * 78}\nHALVORSEN-KAITO (SYNTHETIC)   ENERGY MGMT LEGACY REPORT  RPT-EN-007   PAGE 1\nFACILITY: {fid:<12}  RUN DATE: 05/01/2027\n{'-' * 78}\nPERIOD     METER        CONSUMPTION   UNIT   AMOUNT        CCY\n" +
                   "\n".join(f"{pd.Timestamp(r.billing_period_start):%m/%Y}    {r.meter_id:<12} {r.consumption:>12,.1f}   {r.unit:<5}  {r.total_payable:>12,.2f}  {r.currency}" for r in g2.itertuples()))
    ctx.write("Traditional_IT/Batch_Exports/RPT_EN_007_energy_report.txt", "\n\n".join(rep), kind="legacy", system="EMS_LEGACY")
    logs = []
    ts = pd.date_range("2025-01-01", "2026-12-31", periods=4000)
    for t in ts:
        lvl = rng.choice(["INFO", "INFO", "INFO", "WARN", "ERROR"])
        msg = {"INFO": f"Batch job ZGHG_EXTRACT completed rows={rng.integers(100, 90000)}", "WARN": f"Unit mismatch on meter MTR-{rng.integers(1, 5000):05d}: expected kWh got MWh",
               "ERROR": f"SFTP transfer failed host=sftp.synthetic-utility.example retry={rng.integers(1, 4)}"}[lvl]
        logs.append(f"{t:%Y-%m-%d %H:%M:%S,%f}"[:23] + f" [{lvl}] integration-hub pid={rng.integers(1000, 9999)} {msg}")
    ctx.write("Traditional_IT/Application_Logs/integration_hub.log", "\n".join(logs), kind="log", system="INTEGRATION_HUB")
    wm = ctx.get("water_monthly").head(6000)
    ctx.write("Traditional_IT/Flat_Files/LIMS_wastewater_results.csv", wm[["water_record_id", "facility_id", "period", "cod_mg_l", "bod_mg_l", "tss_mg_l", "ph"]].rename(columns={"cod_mg_l": "COD", "bod_mg_l": "BOD5", "tss_mg_l": "TSS"}).to_csv(index=False), system="LIMS")
    mt = ctx.get("maintenance").head(20000)
    ctx.write("Traditional_IT/Flat_Files/CMMS_WORKORDERS_EXPORT.psv", mt[["cmms_wo", "asset_id", "maintenance_type", "work_date", "downtime_hours", "refrigerant_added_kg"]].assign(work_date=lambda d: d.work_date.dt.strftime("%m/%d/%Y")).to_csv(sep="|", index=False), system="CMMS")
    qi = ctx.get("quality_inspections").head(5000)
    ctx.write("Traditional_IT/Flat_Files/QMS_nonconformance.csv", qi[qi.result != "Pass"].to_csv(index=False), system="QMS")
    pay = ctx.get("commuting_survey")
    ctx.write("Traditional_IT/Mainframe/PAYROLL_SUMMARY_AGG.DAT", "\n".join(f"{r.facility_id:<12}{r.year:04d}{int(r.headcount):07d}{int(r.fte * 100):09d}" for r in pay.itertuples()), kind="legacy", system="PAYROLL_LEGACY")
    ctx.write("Traditional_IT/Batch_Exports/SFTP_exchange_manifest.csv", pd.DataFrame(dict(transfer_id=ids("SFTP-", 500, 5), remote_host="sftp.synthetic-partner.example", direction=rng.choice(["IN", "OUT"], 500),
                                                                                             filename=[f"UTIL_{rng.integers(10 ** 5, 10 ** 6)}.csv" for _ in range(500)], status=rng.choice(["OK", "OK", "OK", "FAILED", "PARTIAL"], 500),
                                                                                             transferred_at=pd.date_range("2022-01-05", "2026-12-28", periods=500))).to_csv(index=False), system="SFTP")
    v1 = ui[ui.billing_period_start.dt.year == 2022].head(2000)[["facility_id", "billing_period_start", "consumption", "unit"]].rename(columns={"facility_id": "Site", "billing_period_start": "Month", "consumption": "Elec (kWh)"})
    v2 = ui[ui.billing_period_start.dt.year == 2024].head(2000)[["facility_id", "meter_id", "billing_period_start", "consumption", "unit", "total_payable"]].rename(columns={"facility_id": "site_code", "billing_period_start": "period", "consumption": "qty", "total_payable": "cost_local"})
    ctx.write("Traditional_IT/Batch_Exports/energy_extract_schema_v1_2022.csv", v1.to_csv(index=False), system="EMS_LEGACY")
    ctx.write("Traditional_IT/Batch_Exports/energy_extract_schema_v2_2024.csv", v2.to_csv(index=False), system="EMS")
    # manual spreadsheet submissions (inconsistent headers)
    for i, fid in enumerate(fac[fac.facility_type == "Manufacturing"].facility_id.head(20)):
        w = ctx.get("waste_records"); w = w[w.facility_id == fid].head(60)
        hdr = [["Waste Stream", "Tonnes", "Method", "Month"], ["type", "qty (kg?)", "disposal", "period"], ["Abfallart", "Menge t", "Verfahren", "Monat"]][i % 3]
        w[["waste_type", "quantity", "disposal_method", "period"]].set_axis(hdr, axis=1).to_excel(ctx.path(f"Traditional_IT/Flat_Files/manual_submissions/{fid}_waste_return.xlsx"), index=False)
        ctx.track(f"Traditional_IT/Flat_Files/manual_submissions/{fid}_waste_return.xlsx", kind="manual_spreadsheet", entity=fid, system="MANUAL")
    # databases
    core = ["suppliers", "materials", "purchase_orders", "po_lines", "goods_receipts", "ap_invoices", "utility_invoices", "meters", "facilities", "emission_factors", "ghg_activities", "customers", "sales_orders", "shipments"]
    for d in DIALECT:
        ddl = [f"-- SYNTHETIC {d} schema export generated for testing\n"]
        for t in core:
            m = ctx.registry[t]
            cols = ",\n".join(f"  {c['name']} {sqlt(d, c['dtype'])}" for c in m["columns"])
            pk = f",\n  CONSTRAINT pk_{t} PRIMARY KEY ({m['pk']})" if m.get("pk") else ""
            ddl.append(f"CREATE TABLE {t} (\n{cols}{pk}\n);")
            for col, ref in (m.get("fks") or {}).items():
                rt, rc = ref.split(".")
                ddl.append(f"ALTER TABLE {t} ADD CONSTRAINT fk_{t}_{col} FOREIGN KEY ({col}) REFERENCES {rt}({rc});")
            ddl.append(f"CREATE INDEX ix_{t}_src ON {t} (source_record_id);" if any(c["name"] == "source_record_id" for c in m["columns"]) else "")
        ctx.write(f"Databases/{d}/schema_ddl.sql", "\n".join(ddl), kind="sql", system=d)
        for t in ["facilities", "meters", "utility_invoices", "suppliers"]:
            df = ctx.get(t).head(1500)
            stmts = [f"INSERT INTO {t} ({', '.join(df.columns)}) VALUES ({', '.join(lit(v) for v in row)});" for row in df.itertuples(index=False)]
            ctx.write(f"Databases/{d}/export_{t}_full.sql", "\n".join(stmts), kind="sql", system=d)
    cdc = []
    for i, r in enumerate(po.head(3000).itertuples()):
        op_ = rng.choice(["I", "U", "U", "D"], p=[.6, .3, .05, .05])
        cdc.append(dict(lsn=f"0000{i:08X}", op=op_, table="purchase_orders", commit_ts=str(pd.Timestamp(r.po_date) + pd.Timedelta(hours=int(rng.integers(1, 200)))), key={"po_id": r.po_id},
                        before=None if op_ == "I" else {"approval_status": "Pending"}, after=None if op_ == "D" else {"approval_status": r.approval_status, "total_net_amount": r.total_net_amount}))
    ctx.write("Databases/PostgreSQL/cdc_purchase_orders.jsonl", "\n".join(json.dumps(c, default=str) for c in cdc), kind="cdc", system="PostgreSQL")
    sup = ctx.get("suppliers")
    h = sup.sample(800, random_state=3)
    scd = pd.concat([h.assign(valid_from="2022-01-01", valid_to="2024-06-30", is_current=False), h.assign(risk_rating=np.where(rng.random(800) < 0.3, "High", h.risk_rating), valid_from="2024-07-01", valid_to="9999-12-31", is_current=True)])
    scd[["supplier_id", "supplier_name", "country_id", "risk_rating", "payment_terms", "valid_from", "valid_to", "is_current"]].to_csv(ctx.path("Databases/SQL_Server/dim_supplier_scd2_history.csv"), index=False)
    ctx.track("Databases/SQL_Server/dim_supplier_scd2_history.csv", kind="snapshot", system="SQL_Server")
    stg = ui.head(5000).astype(str).rename(columns=lambda c: "STG_" + c.upper())
    stg.to_csv(ctx.path("Databases/Oracle/STG_UTILITY_INVOICE_raw.csv"), index=False); ctx.track("Databases/Oracle/STG_UTILITY_INVOICE_raw.csv", kind="staging", system="Oracle")
    arc = ctx.get("ar_invoices"); arc = arc[pd.to_datetime(arc.invoice_date).dt.year == 2022].head(20000).rename(columns={"net_amount": "net_amt"})
    arc.to_csv(ctx.path("Databases/MySQL/archive_ar_invoices_2022_schema_v1.csv"), index=False); ctx.track("Databases/MySQL/archive_ar_invoices_2022_schema_v1.csv", kind="archive", system="MySQL")
    inc = ctx.get("ap_invoices").head(30000)
    inc.iloc[: int(len(inc) * 0.93)].to_csv(ctx.path("Databases/SQL_Server/ap_invoices_incremental_extract_TRUNCATED.csv"), index=False)
    ctx.track("Databases/SQL_Server/ap_invoices_incremental_extract_TRUNCATED.csv", kind="incremental", system="SQL_Server")
    ctx.anom("ap_invoices", inc.invoice_id.values[int(len(inc) * 0.93):], "Completeness", "Incomplete database extract", "Medium", "present in extract", "missing (extract truncated)", "Extract job timed out",
             "Row-count reconciliation vs source", "Re-run extract", family="Data_Inconsistencies", system="SQL_Server")
    # APIs
    apis = [("erp", "/api/v2/purchase-orders", po.head(2000)), ("crm", "/services/data/v58.0/query/Account", ctx.get("customers").head(2000)), ("utility", "/v1/accounts/{acct}/intervals", ui.head(2000)),
            ("supplier_sustainability", "/v1/suppliers/{id}/disclosures", ctx.get("supplier_disclosures").head(2000)), ("fleet", "/fleet/v3/vehicles/fuel", ctx.get("fleet_fuel").head(2000)),
            ("logistics", "/tms/v1/shipments", sh.head(2000)), ("manufacturing", "/mes/v1/lines/daily-kpi", ctx.get("mes_line_daily").head(2000)), ("energy_management", "/ems/v2/meters/readings", ctx.get("energy_daily").head(2000)),
            ("esg_reporting", "/esg/v1/inventory", ctx.get("ghg_inventory")), ("document_management", "/dms/v1/documents", pd.DataFrame(dict(document_id=ids("DOC-", 500, 6), status="indexed")))]
    for name, ep, df in apis:
        evs = []
        recs = json.loads(df.to_json(orient="records", date_format="iso"))
        page = 100
        for p in range(0, len(recs), page):
            t0 = pd.Timestamp("2026-03-01") + pd.Timedelta(minutes=p)
            code = int(rng.choice([200, 200, 200, 200, 206, 429, 500]))
            req = {"request_id": f"req-{name}-{p}", "method": "GET", "endpoint": ep, "params": {"page": p // page + 1, "page_size": page}, "headers": {"Authorization": "Bearer <REDACTED_PLACEHOLDER>", "X-Correlation-Id": f"corr-{rng.integers(10 ** 9)}"}, "timestamp": str(t0)}
            body = recs[p:p + page] if code == 200 else recs[p:p + page // 2] if code == 206 else None
            resp = {"status": code, "timestamp": str(t0 + pd.Timedelta(milliseconds=int(rng.integers(40, 3000)))), "source_system": name.upper(),
                    "pagination": {"page": p // page + 1, "page_size": page, "total_records": len(recs), "next": p + page < len(recs)}, "data": body,
                    "error": {"429": {"code": "RATE_LIMIT", "retry_after_s": 30}, "500": {"code": "UPSTREAM_TIMEOUT"}}.get(str(code))}
            evs.append({"request": req, "response": resp})
            if code in (429, 500):
                evs.append({"request": {**req, "request_id": req["request_id"] + "-retry1"}, "response": {**resp, "status": 200, "data": recs[p:p + page], "error": None, "retry_of": req["request_id"]}})
            if rng.random() < 0.03:
                evs.append({"request": req, "response": resp, "duplicate_delivery": True})
        ctx.write(f"APIs/REST/{name}_api_events.jsonl", "\n".join(json.dumps(e, default=str) for e in evs), kind="api", system=name.upper())
        ctx.write(f"APIs/JSON/{name}_sample_response.json", json.dumps(evs[0], indent=1, default=str), kind="api", system=name.upper())
        ctx.write(f"APIs/API_Logs/{name}_gateway.log", "\n".join(f"{e['request']['timestamp']} {e['request']['method']} {e['request']['endpoint']} status={e['response']['status']} id={e['request']['request_id']}" for e in evs), kind="log", system="API_GATEWAY")
    x = ['<?xml version="1.0"?>', '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><GetConsumptionResponse synthetic="true">']
    for r in ui.head(500).itertuples():
        x.append(f'<Interval meter="{r.meter_id}" start="{pd.Timestamp(r.billing_period_start):%Y-%m-%d}" end="{pd.Timestamp(r.billing_period_end):%Y-%m-%d}" unit="{r.unit}">{r.consumption}</Interval>')
    x.append("</GetConsumptionResponse></soap:Body></soap:Envelope>")
    ctx.write("APIs/XML/utility_provider_soap_response.xml", "\n".join(x), kind="api", system="UTILITY_API")
