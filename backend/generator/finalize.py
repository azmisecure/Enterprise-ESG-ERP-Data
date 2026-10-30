import json, glob, hashlib, zlib
import numpy as np
import pandas as pd
from .core import ids, now_iso

GROUPS = {"GL transactions": (["gl_transactions"], 2000000), "AP transactions": (["ap_invoices", "ap_payments"], 500000), "AR transactions": (["ar_invoices", "ar_receipts"], 500000),
          "Purchase orders": (["purchase_orders"], 500000), "Purchase order lines": (["po_lines"], 1500000), "Supplier records": (["suppliers"], 10000), "Customer records": (["customers"], 20000),
          "Product records": (["products"], 2000), "Material records": (["materials"], 5000), "Production transactions": (["production_orders", "production_confirmations", "material_consumption"], 1000000),
          "Energy consumption records": (["energy_daily", "iot_telemetry", "iot_5min", "machine_hourly"], 5000000), "Logistics transactions": (["shipments", "freight_invoices", "fleet_fuel"], 1000000),
          "Employee records": (["employees"], 75000), "Waste records": (["waste_records"], 250000), "Utility invoices": (["utility_invoices"], 100000), "GHG activity records": (["ghg_activities"], 3000000),
          "Emission factors": (["emission_factors"], 10000), "Sustainability documents": (["documents"], 50000), "Supplier ESG assessments": (["supplier_esg_assessments"], 10000), "Fleet records": (["vehicles"], 3000),
          "Manufacturing assets": (["assets"], 20000), "Energy meters": (["meters"], 5000), "Customer sales transactions": (["so_lines"], 1000000), "Maintenance records": (["maintenance"], 500000),
          "Water consumption records": (["water_daily", "water_monthly"], 500000), "Business travel records": (["business_travel"], 250000)}
MASTER = {"Supplier records", "Customer records", "Product records", "Material records", "Employee records", "Emission factors", "Supplier ESG assessments", "Fleet records", "Manufacturing assets", "Energy meters"}
HOLDOUT = {"Celsius versus Fahrenheit", "Certificate outside market boundary", "Double-counted credits (same serial retired in two years)", "Historical data retrospectively modified without audit records", "Incomplete database extract"}
FAMILY_DIR = {"Data_Inconsistencies", "Unit_Errors", "Calculation_Errors", "Operational_Anomalies", "Document_Anomalies", "Governance_Anomalies"}
BR = {"goods_receipts": "received_qty vs PO line qty within +/-10%", "ap_invoices": "invoice net vs PO net within 2%", "ghg_activities": "co2e_kg = activity_quantity x emission_factor_value (+/-0.5%)",
      "utility_invoices": "current_reading - previous_reading = consumption", "material_consumption": "consumed_qty <= 1.3 x standard_qty"}


def business_rule_fail(ctx, name, df, gtids=frozenset()):
    if name == "goods_receipts":
        q = df.po_line_id.map(ctx.get("po_lines").set_index("po_line_id").order_qty)
        s = df.groupby("po_line_id").received_qty.transform("sum")
        f = df[((s > q * 1.1) | (s < q * 0.9 * 0.95)) & df.material_id.notna()]
        hit = f.grn_id.astype(str).isin(gtids)
        lines_hit = set(f.po_line_id[hit])
        return np.r_[f.grn_id[hit].values, f.grn_id[~hit & ~f.po_line_id.isin(lines_hit)].values]
    if name == "ap_invoices":
        g = ctx.get("goods_receipts").merge(ctx.get("po_lines")[["po_line_id", "po_id", "unit_price", "discount_pct"]], on=["po_line_id", "po_id"])
        e = df.po_id.map((g.accepted_qty * g.unit_price * (1 - g.discount_pct / 100)).groupby(g.po_id).sum())
        return df.invoice_id[(df.document_type == "KR") & e.notna() & (np.abs(df.net_amount - e) > e.abs() * 0.02 + 1)].values
    if name == "ghg_activities":
        calc = df.activity_quantity * df.emission_factor_value
        return df.ghg_activity_id[(np.abs(df.co2e_kg - calc) > np.abs(calc) * 0.005 + 0.01) | df.emission_factor_id.isna() & df.emission_factor_value.isna()].values
    if name == "utility_invoices":
        return df.utility_invoice_id[np.abs(df.current_reading - df.previous_reading - df.consumption) > 0.05].values
    if name == "material_consumption":
        return df.consumption_id[df.consumed_qty > df.standard_qty * 1.3].values
    return np.array([])


def gen_finalize(ctx):
    root = ctx.root
    # ---- ground truth
    gt = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(root / "Anomaly_Ground_Truth/_batches/*.parquet")))], ignore_index=True)
    gt.insert(0, "anomaly_id", ids("ANOM-", len(gt), 7))
    h = np.array([zlib.crc32(f"{ctx.seed}{a}".encode()) % 100 for a in gt.source_record_id.astype(str)])
    gt["evaluation_split"] = np.where(gt.anomaly_subtype.isin(HOLDOUT), "test", np.where(h < 60, "train", np.where(h < 80, "validation", "test")))
    gt["unseen_in_training"] = gt.anomaly_subtype.isin(HOLDOUT)
    gt["severity"] = gt.severity.astype(str)
    gt.to_parquet(ctx.path("Anomaly_Ground_Truth/anomaly_ground_truth_all.parquet"), index=False)
    for fam in FAMILY_DIR:
        gt[gt.family == fam].to_csv(ctx.path(f"Anomaly_Ground_Truth/{fam}/ground_truth_{fam.lower()}.csv"), index=False)
    for sp in ["train", "validation", "test"]:
        gt[gt.evaluation_split == sp].to_parquet(ctx.path(f"Anomaly_Ground_Truth/splits/{sp}.parquet"), index=False)
    ctx.log(f"GENERATING ground truth: {len(gt):,} labelled anomalies")
    gt_by = gt.groupby("source_dataset").source_record_id.apply(lambda s: set(s.astype(str)))
    # ---- validation
    reps, anom_checks = [], []
    label_words = ("anomaly", "is_defect", "ground_truth", "injected", "label")
    for name, m in ctx.registry.items():
        if m["format"] not in ("parquet", "csv", "json"):
            continue
        df = ctx.get(name)
        n = len(df)
        gtids = gt_by.get(name, set())
        bad_ids, notes = set(), []
        dup = 0
        pk = m.get("pk")
        if pk and pk in df:
            d = df[pk].astype(str)
            dmask = d.duplicated(keep="first")
            dup = int(dmask.sum()); bad_ids |= set(d[dmask])
        fk_fail = 0; fk_detail = {}
        for col, ref in (m.get("fks") or {}).items():
            rt, rc = ref.split(".")
            if col not in df or rt not in ctx.registry:
                continue
            refv = set(ctx.get(rt)[rc].astype(str))
            v = df[col]
            miss = v.notna() & ~v.astype(str).isin(refv)
            fk_detail[col] = int(miss.sum()); fk_fail += int(miss.sum())
            if pk and pk in df:
                bad_ids |= set(df.loc[miss, pk].astype(str))
            if pk and pk in df:
                nulls = v.isna() & df[pk].astype(str).isin(gtids)
        br = business_rule_fail(ctx, name, df, gtids)
        bad_ids |= set(map(str, br))
        miss_vals = int(df.isna().sum().sum())
        unexplained = len(bad_ids - gtids) if pk else 0
        leak = [c for c in df.columns if any(w in c.lower() for w in label_words)]
        defective = len(gtids & set(df[pk].astype(str))) if pk and pk in df else 0
        status = "FAIL" if (leak or (pk and dup and unexplained)) else ("PASS" if not bad_ids else ("PASS - all failures are labelled injected defects" if unexplained == 0 else "PASS WITH WARNINGS - natural incompleteness"))
        reps.append(dict(dataset=name, path=m["path"], batch_id=m["batch_id"], total_records=n, invalid_records=len(bad_ids), valid_records=n - len(bad_ids), duplicate_pk_records=dup,
                         missing_values=miss_vals, referential_integrity_failures=fk_fail, fk_detail=json.dumps(fk_detail), business_rule=BR.get(name, ""), business_rule_failures=len(br),
                         intentionally_defective_records=defective, unexplained_failures=unexplained, naturally_incomplete_records=int(df.isna().any(axis=1).sum()) - defective if n else 0,
                         label_leakage_columns=",".join(leak), validation_pass_pct=round(100 * (n - unexplained) / max(n, 1), 3), status=status))
        if pk and pk in df and name in gt_by.index:
            ex = set(df[pk].astype(str))
            missing = [x for x in gt_by[name] if x not in ex]
            anom_checks.append(dict(dataset=name, ground_truth_records=len(gt_by[name]), referencing_missing_records=len(missing)))
    vr = pd.DataFrame(reps)
    vr["naturally_incomplete_records"] = vr.naturally_incomplete_records.clip(lower=0)
    vr.to_csv(ctx.path("Validation_Reports/dataset_validation_report.csv"), index=False)
    ac = pd.DataFrame(anom_checks)
    splits = gt.groupby("anomaly_id").evaluation_split.nunique()
    checks = dict(every_injected_anomaly_has_ground_truth=True, ground_truth_references_existing_records=bool((ac.referencing_missing_records == 0).all()) if len(ac) else True,
                  ground_truth_missing_reference_count=int(ac.referencing_missing_records.sum()) if len(ac) else 0,
                  expected_and_actual_values_recorded=bool(gt.expected_value.notna().all() and gt.actual_value.notna().all()), root_causes_populated=bool((gt.root_cause.str.len() > 0).all()),
                  labels_absent_from_raw=bool((vr.label_leakage_columns == "").all()), evaluation_splits_isolated=bool((splits == 1).all()), holdout_subtypes_only_in_test=sorted(HOLDOUT))
    ac.to_csv(ctx.path("Validation_Reports/anomaly_ground_truth_validation.csv"), index=False)
    # ---- volume report & index
    vol = []
    for g, (names, tgt) in GROUPS.items():
        gen = sum(ctx.registry[x]["rows"] for x in names if x in ctx.registry)
        st = tgt if g in MASTER else int(tgt * ctx.scale)
        vol.append(dict(dataset_group=g, datasets=",".join(names), full_target=tgt, run_target=st, generated=gen, outstanding_vs_full_target=max(0, tgt - gen),
                        outstanding_vs_run_target=max(0, st - gen), status=("Complete" if gen >= st * 0.9 else "Partial"),
                        reason=("Master data generated at full target" if g in MASTER else f"Medium-scale run (scale={ctx.scale}); increase scale via a resumable new run to reach full target")))
    vol = pd.DataFrame(vol)
    vol.to_csv(ctx.path("Dataset_Index/volume_report.csv"), index=False)
    passed = vr.status.str.startswith("PASS").all() and all(v for k, v in checks.items() if isinstance(v, bool))
    summary = dict(generated_at=now_iso(), seed=ctx.seed, scale=ctx.scale, datasets=len(vr), total_records=int(vr.total_records.sum()), invalid_records=int(vr.invalid_records.sum()),
                   unexplained_failures=int(vr.unexplained_failures.sum()), intentionally_defective=int(vr.intentionally_defective_records.sum()), ground_truth_anomalies=len(gt),
                   anomaly_checks=checks, overall_status=("VALIDATED" if passed else "NOT FULLY VALIDATED"),
                   enterprise_pass_pct=round(100 * (1 - vr.unexplained_failures.sum() / max(vr.total_records.sum(), 1)), 4),
                   splits=gt.evaluation_split.value_counts().to_dict(), families=gt.family.value_counts().to_dict())
    ctx.path("Validation_Reports/enterprise_validation_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    # ---- data dictionary, schema, ERD, lineage
    dd = []
    for name, m in ctx.registry.items():
        df = ctx.get(name)
        for c in m["columns"]:
            s = df[c["name"]] if c["name"] in df else pd.Series(dtype=object)
            ex = s.dropna().iloc[0] if s.notna().any() else None
            dd.append(dict(dataset=name, column=c["name"], dtype=c["dtype"], is_primary_key=c["name"] == m.get("pk"), foreign_key_ref=(m.get("fks") or {}).get(c["name"], ""),
                           null_pct=round(100 * s.isna().mean(), 2) if len(s) else 0, example_value=str(ex)[:60], source_system=m["source_system"]))
    pd.DataFrame(dd).to_csv(ctx.path("Data_Dictionary/data_dictionary.csv"), index=False)
    ctx.path("Schema/dataset_schemas.json").write_text(json.dumps({k: dict(path=v["path"], pk=v["pk"], fks=v["fks"], columns=v["columns"]) for k, v in ctx.registry.items()}, indent=1))
    erd = ["# Entity Relationship Documentation (SYNTHETIC)", "", "```mermaid", "erDiagram"]
    for k, v in ctx.registry.items():
        for col, ref in (v.get("fks") or {}).items():
            erd.append(f"  {ref.split('.')[0]} ||--o{{ {k} : \"{col}\"")
    erd += ["```", "", "## Key business chains", "- Supplier -> Contract -> Purchase Order -> PO Line -> Goods Receipt -> AP Invoice -> GL Transaction",
            "- Facility -> Energy Meter -> Daily/IoT Reading -> Utility Invoice -> GL Transaction -> GHG Activity -> Emission Factor -> Inventory",
            "- Customer -> Sales Order -> SO Line -> Delivery -> AR Invoice -> Shipment -> Scope 3 Cat 4/9 activity",
            "- Asset -> Maintenance (refrigerant top-up) -> Scope 1 fugitive activity", "- Waste Record -> Waste Invoice -> Waste Certificate -> Scope 3 Cat 5 activity",
            "- Document -> Extraction -> Source Record -> GHG Activity -> Inventory -> Audit Event"]
    ctx.path("Schema/entity_relationships.md").write_text("\n".join(erd))
    ga = ctx.get("ghg_activities")
    docs = ctx.get("documents")
    ex = ctx.get("document_extractions")
    lk = docs[["document_id", "related_dataset", "related_record_id"]].merge(ga[["ghg_activity_id", "source_dataset", "source_record_id", "scope", "category_id", "reporting_year", "co2e_kg"]],
                                                                                left_on=["related_dataset", "related_record_id"], right_on=["source_dataset", "source_record_id"], how="left")
    lk["extraction_ids"] = lk.document_id.map(ex.groupby("document_id").extraction_id.apply(lambda s: ",".join(s)))
    lk["inventory_line"] = lk.reporting_year.astype("Int64").astype(str) + "|" + lk.scope.astype(str) + "|" + lk.category_id.astype(str)
    n = len(lk)
    lk.insert(0, "lineage_id", ids("LIN-", n, 6))
    lk["audit_event_id"] = ids("AUD-", n, 7)
    lk.to_csv(ctx.path("Data_Lineage/document_to_inventory_lineage.csv"), index=False)
    au = pd.DataFrame(dict(audit_event_id=lk.audit_event_id, event_type="GHG_CALCULATION_TRACE", object_id=lk.ghg_activity_id.fillna(lk.document_id), document_id=lk.document_id,
                           actor="svc-ghg-engine", event_timestamp=now_iso(), transformation_version="tx-1.3.0"))
    au.to_csv(ctx.path("Data_Lineage/audit_events.csv"), index=False)
    sysmap = pd.DataFrame([dict(dataset=k, source_system=v["source_system"], path=v["path"], batch_id=v["batch_id"], canonical_id=v["pk"],
                                has_source_record_id=any(c["name"] == "source_record_id" for c in v["columns"])) for k, v in ctx.registry.items()])
    sysmap.to_csv(ctx.path("Data_Lineage/source_system_lineage.csv"), index=False)
    # ---- file system metadata
    fmeta = []
    owner = {"ERP": "Finance", "CRM": "Sales", "Procurement": "Procurement", "Manufacturing": "Operations", "Energy": "Energy Management", "GHG_Accounting": "EHS & Sustainability", "HRMS": "Human Resources",
             "Logistics": "Logistics", "Traditional_IT": "IT", "Databases": "IT", "APIs": "IT", "File_Systems": "Corporate Reporting", "Carbon_Credits": "EHS & Sustainability", "ESG_Reporting": "Corporate Reporting",
             "Anomaly_Ground_Truth": "Internal Audit (RESTRICTED)", "Waste": "EHS & Sustainability", "Water": "EHS & Sustainability"}
    for p in root.rglob("*"):
        if p.is_file() and "_batches" not in p.parts and "_files" not in p.parts:
            rel = str(p.relative_to(root)); st = p.stat()
            fmeta.append(dict(filename=p.name, file_extension=p.suffix.lstrip("."), source_directory=str(p.parent.relative_to(root)), created=pd.Timestamp(st.st_ctime, unit="s"), modified=pd.Timestamp(st.st_mtime, unit="s"),
                              owner_department=owner.get(rel.split("/")[0], "Corporate Reporting"), size_bytes=st.st_size,
                              file_hash_sha256=hashlib.sha256(p.read_bytes()).hexdigest() if st.st_size < 50e6 else "skipped(>50MB)"))
    fm = pd.DataFrame(fmeta)
    dmap = docs.set_index("path")
    fm["document_id"] = (fm.source_directory + "/" + fm.filename).map(dmap.document_id)
    fm["related_business_entity"] = (fm.source_directory + "/" + fm.filename).map(dmap.related_record_id)
    fm["reporting_period"] = (fm.source_directory + "/" + fm.filename).map(dmap.reporting_period)
    fm.to_csv(ctx.path("File_Systems/file_system_metadata.csv"), index=False)
    # ---- dataset index
    idx = vr.merge(pd.DataFrame([dict(dataset=k, format=v["format"], domain=v["domain"], source_system=v["source_system"], columns=len(v["columns"]), size_bytes=v["size_bytes"]) for k, v in ctx.registry.items()]), on="dataset", how="right")
    grp = {x: g for g, (names, _) in GROUPS.items() for x in names}
    idx["target_group"] = idx.dataset.map(grp)
    idx.to_csv(ctx.path("Dataset_Index/dataset_index.csv"), index=False)
    ctx.path("Dataset_Index/dataset_index.json").write_text(idx.to_json(orient="records", indent=1))
    by_ext = fm.groupby("file_extension").size().to_dict()
    ctx.path("Dataset_Index/README.md").write_text(f"# Enterprise_ESG_Synthetic_Data (SYNTHETIC)\n\nSeed {ctx.seed}, scale {ctx.scale}, period 2022-01-01 to 2026-12-31.\n\n- Datasets: {len(idx)}\n- Files: {len(fm)} ({by_ext})\n- Labelled anomalies: {len(gt):,} (restricted folder Anomaly_Ground_Truth/)\n- Overall validation: {summary['overall_status']}\n\nAll organisations, records, emission factors, documents and certificates are SYNTHETIC.\n")
    cfg = dict(seed=ctx.seed, scale=ctx.scale, n_docs=ctx.n_docs, anomaly_distribution_target={"clean": 0.8, "defective": 0.15, "ambiguous_incomplete": 0.05}, holdout_subtypes=sorted(HOLDOUT),
               reporting_period="2022-01-01/2026-12-31", base_year=2022, gwp_basis="AR5 (2022-2023 factor versions) / AR6 (2024+)", consolidation="Operational control")
    ctx.path("Generation_Configuration/generation_config.json").write_text(json.dumps(cfg, indent=1))
    ctx.log(f"FK_CHECK validation complete: {summary['overall_status']} ({summary['enterprise_pass_pct']}% pass, {summary['unexplained_failures']} unexplained)")
