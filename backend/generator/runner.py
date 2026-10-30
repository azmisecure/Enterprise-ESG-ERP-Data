import argparse, json, os, sys, traceback, signal
from pathlib import Path
from .core import Ctx, now_iso, timer

BATCHES = [
    ("B01", "Enterprise master data & organisational hierarchy", "master:gen_enterprise", []),
    ("B02", "Source-system master data (suppliers, customers, products, materials, BOM, assets, meters, fleet, employees)", "master:gen_source_master", ["B01"]),
    ("B03", "Emission-factor reference database (synthetic)", "ef:gen_emission_factors", ["B02"]),
    ("B04", "Procurement & accounts payable", "erp:gen_procurement", ["B02"]),
    ("B05", "CRM, sales & accounts receivable", "erp:gen_sales", ["B02"]),
    ("B06", "Manufacturing (ERP PP, MES, maintenance, quality)", "erp:gen_manufacturing", ["B05"]),
    ("B07", "Energy, utilities, water, waste & IoT telemetry", "ops:gen_energy", ["B06"]),
    ("B08", "Logistics, fleet, HRMS & business travel", "ops:gen_logistics_hr", ["B04", "B05"]),
    ("B09", "Finance general ledger, trial balance & statements", "finance:gen_finance", ["B04", "B05", "B07", "B08"]),
    ("B10", "GHG accounting Scope 1, 2 & 3 (15 categories)", "ghg:gen_ghg", ["B03", "B07", "B08", "B09"]),
    ("B11", "Supplier ESG, ESG performance, decarbonisation & carbon credits", "esg:gen_esg", ["B10"]),
    ("B12", "Traditional IT, legacy files, databases & APIs", "legacy:gen_legacy", ["B09", "B10"]),
    ("B13", "Business documents (PDF, DOCX, XLSX, EML, TXT, MD)", "docs:gen_documents", ["B11"]),
    ("B14", "Ground truth, lineage, dictionary, validation & dataset index", "finalize:gen_finalize", ["B13"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--scale", type=float, default=0.1)
    ap.add_argument("--docs", type=int, default=3000)
    ap.add_argument("--only", default="")
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)
    cfg_dir = root / "Generation_Configuration"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    man_p, st_p, log_p = cfg_dir / "batch_manifest.json", cfg_dir / "run_status.json", cfg_dir / "generation.log"
    config = dict(seed=a.seed, scale=a.scale, n_docs=a.docs, period="2022-01-01/2026-12-31", schema_version="4.2.0")
    man = json.loads(man_p.read_text()) if man_p.exists() else {}
    if a.fresh or man.get("config") != config:
        import shutil
        for d in root.iterdir():
            if d.name != "Generation_Configuration":
                shutil.rmtree(d) if d.is_dir() else d.unlink()
        man = dict(config=config, batches={})
        log_p.write_text("")
    logf = open(log_p, "a")

    def log(msg, level="INFO"):
        if msg.startswith(("GENERATING", "WARN", "FK_CHECK", "ERROR")):
            level, msg = msg.split(" ", 1)
        line = f"{now_iso()} [{level}] {msg}"
        logf.write(line + "\n"); logf.flush()
        print(line, flush=True)

    def status(**kw):
        s = json.loads(st_p.read_text()) if st_p.exists() else {}
        s.update(kw, pid=os.getpid(), updated=now_iso(), config=config)
        st_p.write_text(json.dumps(s, indent=1))

    def stop(*_):
        status(state="stopped")
        log("Generation paused by operator; resume continues from last completed checkpoint", "WARN")
        sys.exit(0)
    signal.signal(signal.SIGTERM, stop)
    ctx = Ctx(root, a.seed, a.scale, a.docs, log)
    status(state="running", started=now_iso(), total_batches=len(BATCHES))
    only = set(a.only.split(",")) if a.only else None
    import importlib
    for i, (bid, name, fn, deps) in enumerate(BATCHES):
        b = man["batches"].get(bid, {})
        if only and bid not in only:
            continue
        if b.get("status") == "completed" and not only:
            log(f"{bid} already completed at checkpoint - skipping (resume)")
            continue
        missing = [d for d in deps if man["batches"].get(d, {}).get("status") != "completed"]
        if missing:
            log(f"{bid} blocked: parent batches not completed {missing}", "ERROR")
            status(state="failed", error=f"{bid} parents missing")
            return
        status(current_batch=bid, current_name=name, progress=round(100 * i / len(BATCHES), 1))
        log(f"=== {bid}: {name} (seed={a.seed}, scale={a.scale}) ===")
        t = timer()
        before = dict(ctx.registry)
        ctx.start_batch(bid)
        man["batches"][bid] = dict(batch_id=bid, objective=name, status="running", started=now_iso(), random_seed=a.seed, parent_batches=deps, schema_version="4.2.0")
        man_p.write_text(json.dumps(man, indent=1))
        try:
            mod, f = fn.split(":")
            getattr(importlib.import_module(f"generator.{mod}"), f)(ctx)
            ctx.flush()
        except Exception as e:
            log(f"{bid} failed: {e}\n{traceback.format_exc()}", "ERROR")
            man["batches"][bid]["status"] = "failed"
            man_p.write_text(json.dumps(man, indent=1))
            status(state="failed", error=str(e))
            return
        outs = [k for k, v in ctx.registry.items() if v.get("batch_id") == bid]
        man["batches"][bid].update(status="completed", finished=now_iso(), duration_s=t(), datasets=outs,
                                   record_count=sum(ctx.registry[k]["rows"] for k in outs), output_files=[ctx.registry[k]["path"] for k in outs],
                                   validation_status="pending (validated in B14)")
        man_p.write_text(json.dumps(man, indent=1))
        log(f"{bid} completed in {t()}s: {len(outs)} datasets, {man['batches'][bid]['record_count']:,} records")
    vp = root / "Validation_Reports/dataset_validation_report.csv"
    if vp.exists():
        import pandas as pd
        vr = pd.read_csv(vp).set_index("dataset").status
        for bid, b in man["batches"].items():
            st = [vr.get(d, "PASS") for d in b.get("datasets", [])]
            b["validation_status"] = "FAIL" if any(str(x).startswith("FAIL") for x in st) else ("PASS WITH WARNINGS" if any("WARN" in str(x) for x in st) else "PASS")
        man_p.write_text(json.dumps(man, indent=1))
    status(state="completed", progress=100.0, current_batch=None, finished=now_iso())
    log("Generation run completed")


if __name__ == "__main__":
    main()
