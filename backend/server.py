from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import datetime, timezone
import os, json, signal, subprocess, sys, threading, zipfile, uuid, logging
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
DATA = Path(os.environ["DATA_ROOT"])
EXPORT_DIR = DATA.parent / "exports"
app = FastAPI()
api = APIRouter(prefix="/api")
logging.basicConfig(level=logging.INFO)


class GenerateRequest(BaseModel):
    seed: int = 42
    scale: float = Field(0.1, gt=0, le=1)
    n_docs: int = Field(3000, ge=50, le=20000)
    fresh: bool = False


def rjson(p, default=None):
    p = DATA / p
    return json.loads(p.read_text()) if p.exists() else default


def clean(df):
    return json.loads(df.replace({np.nan: None}).to_json(orient="records", date_format="iso"))


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


@api.get("/")
async def root():
    return {"service": "Enterprise ESG Synthetic Data Generator", "data_root": str(DATA)}


@api.post("/generate")
async def generate(req: GenerateRequest):
    st = rjson("Generation_Configuration/run_status.json", {})
    if st.get("state") == "running" and pid_alive(st.get("pid", -1)):
        raise HTTPException(409, "A generation run is already in progress")
    DATA.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "generator.runner", "--root", str(DATA), "--seed", str(req.seed), "--scale", str(req.scale), "--docs", str(req.n_docs)]
    if req.fresh:
        cmd.append("--fresh")
    log = open(DATA.parent / "runner_stdout.log", "a")
    proc = subprocess.Popen(cmd, cwd=str(ROOT_DIR), stdout=log, stderr=log, start_new_session=True)
    run = dict(run_id=str(uuid.uuid4()), pid=proc.pid, seed=req.seed, scale=req.scale, n_docs=req.n_docs, fresh=req.fresh, started_at=datetime.now(timezone.utc).isoformat())
    await db.generation_runs.insert_one(dict(run))
    return run


@api.post("/generate/stop")
async def stop():
    st = rjson("Generation_Configuration/run_status.json", {})
    pid = st.get("pid")
    if not pid or not pid_alive(pid):
        raise HTTPException(400, "No active run")
    os.kill(pid, signal.SIGTERM)
    return {"stopped": pid}


@api.get("/status")
async def status(log_lines: int = 250):
    st = rjson("Generation_Configuration/run_status.json", {"state": "idle"})
    if st.get("state") == "running" and not pid_alive(st.get("pid", -1)):
        st["state"] = "interrupted"
    man = rjson("Generation_Configuration/batch_manifest.json", {"batches": {}})
    lp = DATA / "Generation_Configuration/generation.log"
    lines = lp.read_text().splitlines()[-log_lines:] if lp.exists() else []
    runs = await db.generation_runs.find({}, {"_id": 0}).sort("started_at", -1).to_list(10)
    from generator.runner import BATCHES
    batches = [dict(batch_id=b, name=n, dependencies=d, **{k: v for k, v in man["batches"].get(b, {}).items() if k not in ("output_files", "batch_id")}) for b, n, _, d in BATCHES]
    return dict(status=st, config=man.get("config"), batches=batches, log=lines, runs=runs)


@api.get("/index")
async def index():
    reg = rjson("Dataset_Index/_registry.json", {})
    vr = DATA / "Validation_Reports/dataset_validation_report.csv"
    v = pd.read_csv(vr).set_index("dataset") if vr.exists() else pd.DataFrame()
    rows = []
    for k, m in reg.items():
        r = dict(name=k, path=m["path"], format=m["format"], rows=m["rows"], domain=m["domain"], batch_id=m["batch_id"], source_system=m["source_system"], columns=len(m["columns"]),
                 size_bytes=m["size_bytes"], pk=m["pk"], fks=m["fks"])
        if k in v.index:
            r.update(status=v.loc[k, "status"], validation_pass_pct=float(v.loc[k, "validation_pass_pct"]))
        rows.append(r)
    vol = DATA / "Dataset_Index/volume_report.csv"
    return dict(datasets=rows, volume=clean(pd.read_csv(vol)) if vol.exists() else [])


@api.get("/datasets/{name}/preview")
async def preview(name: str, limit: int = Query(50, le=500), offset: int = 0):
    reg = rjson("Dataset_Index/_registry.json", {})
    if name not in reg:
        raise HTTPException(404, "Dataset not found")
    m = reg[name]
    p = DATA / m["path"]
    if m["format"] == "parquet":
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(p)
        df = pf.read_row_group(0).to_pandas().iloc[offset:offset + limit]
    elif m["format"] == "json":
        df = pd.read_json(p).iloc[offset:offset + limit]
    else:
        df = pd.read_csv(p, nrows=offset + limit, low_memory=False).iloc[offset:]
    return dict(name=name, meta={k: m[k] for k in ("path", "format", "rows", "pk", "fks", "columns", "source_system", "batch_id", "description")}, rows=clean(df))


@api.get("/validation")
async def validation():
    vr = DATA / "Validation_Reports/dataset_validation_report.csv"
    return dict(summary=rjson("Validation_Reports/enterprise_validation_summary.json"), datasets=clean(pd.read_csv(vr)) if vr.exists() else [])


def gt_df():
    p = DATA / "Anomaly_Ground_Truth/anomaly_ground_truth_all.parquet"
    if not p.exists():
        raise HTTPException(404, "Ground truth not generated yet")
    return pd.read_parquet(p)


@api.get("/anomalies/summary")
async def anomaly_summary():
    g = gt_df()
    return dict(total=len(g), by_family=g.family.value_counts().to_dict(), by_split=g.evaluation_split.value_counts().to_dict(), by_severity=g.severity.value_counts().to_dict(),
                by_subtype=clean(g.groupby(["family", "anomaly_subtype"]).size().rename("count").reset_index().sort_values("count", ascending=False)))


@api.get("/anomalies")
async def anomalies(clearance: bool = False, family: str = "", split: str = "", severity: str = "", search: str = "", page: int = 1, page_size: int = Query(50, le=200)):
    if not clearance:
        raise HTTPException(403, "Ground-truth labels are restricted. Enable 'View Ground Truth' clearance.")
    g = gt_df()
    if family: g = g[g.family == family]
    if split: g = g[g.evaluation_split == split]
    if severity: g = g[g.severity == severity]
    if search: g = g[g.anomaly_subtype.str.contains(search, case=False) | g.source_record_id.astype(str).str.contains(search, case=False)]
    return dict(total=len(g), page=page, rows=clean(g.iloc[(page - 1) * page_size: page * page_size]))


@api.get("/ghg/summary")
async def ghg_summary():
    p = DATA / "GHG_Accounting/Calculation_Results/annual_ghg_inventory.csv"
    if not p.exists():
        raise HTTPException(404, "GHG inventory not generated yet")
    inv = pd.read_csv(p)
    years = sorted(inv.reporting_year.unique())
    trend = []
    for y in years:
        t = inv[inv.reporting_year == y]
        trend.append(dict(year=int(y), scope1=round(t[t.scope == "Scope 1"].tco2e.sum(), 1), scope2_location=round(t[(t.scope == "Scope 2") & (t.scope2_method == "location-based")].tco2e.sum(), 1),
                          scope2_market=round(t[(t.scope == "Scope 2") & (t.scope2_method == "market-based")].tco2e.sum(), 1), scope3=round(t[t.scope == "Scope 3"].tco2e.sum(), 1)))
    s3 = inv[inv.scope == "Scope 3"].groupby(["category_id"]).tco2e.sum().reset_index()
    led = DATA / "Carbon_Credits/neutralisation_ledger.csv"
    dec = DATA / "Decarbonisation/decarbonisation_opportunities.csv"
    d = pd.read_csv(dec) if dec.exists() else pd.DataFrame()
    top = d[d.scenario == "Base"].groupby("opportunity_name").agg(reduction=("interaction_adjusted_reduction_tco2e", "sum"), capex=("implementation_cost_usd", "sum"), savings=("annual_cost_savings_usd", "sum"), n=("opportunity_id", "count")).reset_index().sort_values("reduction", ascending=False) if len(d) else d
    kp = DATA / "ESG_Reporting/esg_kpi_summary.csv"
    return dict(trend=trend, scope3_categories=clean(s3), ledger=clean(pd.read_csv(led)) if led.exists() else [], decarbonisation=clean(top), kpis=clean(pd.read_csv(kp)) if kp.exists() else [])


@api.get("/documents")
async def documents(doc_type: str = "", fmt: str = "", page: int = 1, page_size: int = Query(48, le=200)):
    p = DATA / "File_Systems/document_registry.csv"
    if not p.exists():
        return dict(total=0, rows=[], types=[], formats=[])
    d = pd.read_csv(p)
    types, fmts = sorted(d.document_type.unique()), sorted(d.file_format.unique())
    if doc_type: d = d[d.document_type == doc_type]
    if fmt: d = d[d.file_format == fmt]
    return dict(total=len(d), types=types, formats=fmts, rows=clean(d.iloc[(page - 1) * page_size: page * page_size]))


@api.get("/tree")
async def tree():
    if not DATA.exists():
        return []
    out = []
    for top in sorted(p for p in DATA.iterdir() if p.is_dir()):
        files = [f for f in top.rglob("*") if f.is_file() and "_batches" not in f.parts and "_files" not in f.parts]
        subs = sorted({f.relative_to(top).parts[0] for f in files if len(f.relative_to(top).parts) > 1})
        exts = pd.Series([f.suffix.lstrip(".") for f in files]).value_counts().to_dict() if files else {}
        out.append(dict(name=top.name, files=len(files), size_bytes=sum(f.stat().st_size for f in files), subfolders=subs, extensions=exts))
    return out


@api.get("/files/download")
async def download(path: str):
    p = (DATA / path).resolve()
    if not str(p).startswith(str(DATA.resolve())) or not p.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(p, filename=p.name)


EXPORT = {"state": "idle"}


def build_zip(include_gt: bool):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    name = f"Enterprise_ESG_Synthetic_Data{'_with_ground_truth' if include_gt else ''}.zip"
    out = EXPORT_DIR / name
    try:
        files = [f for f in DATA.rglob("*") if f.is_file() and "_batches" not in f.parts and "_files" not in f.parts and (include_gt or "Anomaly_Ground_Truth" not in f.parts)]
        EXPORT.update(state="building", total=len(files), done=0, file=name)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as z:
            for i, f in enumerate(files):
                z.write(f, "Enterprise_ESG_Synthetic_Data/" + str(f.relative_to(DATA)))
                EXPORT["done"] = i + 1
        EXPORT.update(state="ready", size_bytes=out.stat().st_size, finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as e:
        EXPORT.update(state="failed", error=str(e))


@api.post("/export")
async def export(include_ground_truth: bool = False):
    if EXPORT.get("state") == "building":
        raise HTTPException(409, "Export already building")
    threading.Thread(target=build_zip, args=(include_ground_truth,), daemon=True).start()
    EXPORT.update(state="building", done=0, total=0)
    return EXPORT


@api.get("/export/status")
async def export_status():
    return EXPORT


@api.get("/export/download")
async def export_download():
    if EXPORT.get("state") != "ready":
        raise HTTPException(400, "Export not ready")
    p = EXPORT_DIR / EXPORT["file"]
    return FileResponse(p, filename=p.name, media_type="application/zip")


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
