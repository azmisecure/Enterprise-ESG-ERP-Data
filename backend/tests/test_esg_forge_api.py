# Regression tests for Enterprise ESG Synthetic Data Generator API
import os, time, pytest, requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
S = requests.Session()


# --- Status / batches ---
def test_status():
    r = S.get(f"{API}/status", timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d["status"]["state"] == "completed"
    assert d["config"]["seed"] == 42 and d["config"]["scale"] == 0.1
    ids = [b["batch_id"] for b in d["batches"]]
    assert ids == [f"B{i:02d}" for i in range(1, 15)]
    assert all(b.get("status") == "completed" for b in d["batches"])
    assert len(d["log"]) > 0


# --- Dataset index ---
def test_index():
    r = S.get(f"{API}/index", timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert 100 <= len(d["datasets"]) <= 120, len(d["datasets"])
    x = d["datasets"][0]
    for k in ("name", "rows", "pk", "fks", "status", "path", "format"):
        assert k in x
    assert isinstance(d["volume"], list) and len(d["volume"]) > 0


# --- Preview ---
@pytest.mark.parametrize("name,fmt", [("utility_invoices", "parquet"), ("ghg_activities", "parquet"), ("facilities", "csv"), ("enterprise", "json")])
def test_preview(name, fmt):
    r = S.get(f"{API}/datasets/{name}/preview?limit=20", timeout=60)
    assert r.status_code == 200, r.text[:200]
    d = r.json()
    assert d["meta"]["format"] == fmt
    assert 0 < len(d["rows"]) <= 20


def test_preview_unknown():
    assert S.get(f"{API}/datasets/nope_xyz/preview", timeout=30).status_code == 404


def test_preview_limit_over_max():
    assert S.get(f"{API}/datasets/facilities/preview?limit=1000", timeout=30).status_code == 422


# --- Validation ---
def test_validation():
    r = S.get(f"{API}/validation", timeout=60)
    d = r.json()
    assert d["summary"]["overall_status"] == "VALIDATED"
    assert len(d["datasets"]) > 50


# --- Anomalies ---
def test_anomalies_forbidden():
    assert S.get(f"{API}/anomalies", timeout=30).status_code == 403


def test_anomalies_with_filters():
    r = S.get(f"{API}/anomalies", params={"clearance": "true"}, timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d["total"] > 0 and len(d["rows"]) == 50
    row = d["rows"][0]
    fam, split, sev = row["family"], row["evaluation_split"], row["severity"]
    for k, v, col in (("family", fam, "family"), ("split", split, "evaluation_split"), ("severity", sev, "severity")):
        rr = S.get(f"{API}/anomalies", params={"clearance": "true", k: v}, timeout=60).json()
        assert rr["total"] > 0 and all(x[col] == v for x in rr["rows"])
        assert rr["total"] <= d["total"]
    sub = row["anomaly_subtype"]
    rr = S.get(f"{API}/anomalies", params={"clearance": "true", "search": sub}, timeout=60).json()
    assert rr["total"] > 0 and all(sub.lower() in x["anomaly_subtype"].lower() or sub.lower() in str(x["source_record_id"]).lower() for x in rr["rows"])
    p2 = S.get(f"{API}/anomalies", params={"clearance": "true", "page": 2}, timeout=60).json()
    assert p2["rows"][0]["anomaly_id"] != row["anomaly_id"]


def test_anomaly_summary():
    d = S.get(f"{API}/anomalies/summary", timeout=60).json()
    assert set(d["by_split"].keys()) == {"train", "validation", "test"}
    assert d["total"] == sum(d["by_split"].values())


# --- GHG ---
def test_ghg_summary():
    d = S.get(f"{API}/ghg/summary", timeout=60).json()
    assert [t["year"] for t in d["trend"]] == [2022, 2023, 2024, 2025, 2026]
    cats = sorted(c["category_id"] for c in d["scope3_categories"])
    assert cats == [f"S3-C{i:02d}" for i in range(1, 16)]
    assert len(d["ledger"]) > 0 and len(d["decarbonisation"]) > 0


# --- Documents / file download ---
def test_documents_and_download():
    d = S.get(f"{API}/documents", timeout=60).json()
    assert d["total"] > 3000 and d["types"] and d["formats"]
    f = "pdf" if "pdf" in d["formats"] else d["formats"][0]
    df = S.get(f"{API}/documents", params={"fmt": f}, timeout=60).json()
    assert all(x["file_format"] == f for x in df["rows"]) and df["total"] < d["total"]
    t = d["types"][0]
    dt = S.get(f"{API}/documents", params={"doc_type": t}, timeout=60).json()
    assert all(x["document_type"] == t for x in dt["rows"])
    magic = {"pdf": b"%PDF", "docx": b"PK", "xlsx": b"PK"}
    for fm, mg in magic.items():
        rows = S.get(f"{API}/documents", params={"fmt": fm}, timeout=60).json()["rows"]
        if not rows:
            continue
        r = S.get(f"{API}/files/download", params={"path": rows[0]["path"]}, timeout=60)
        assert r.status_code == 200 and r.content[:len(mg)] == mg, fm


@pytest.mark.parametrize("p", ["../../etc/passwd", "../../../../etc/passwd", "/etc/passwd"])
def test_path_traversal(p):
    assert S.get(f"{API}/files/download", params={"path": p}, timeout=30).status_code == 404


def test_tree():
    d = S.get(f"{API}/tree", timeout=60).json()
    names = [x["name"] for x in d]
    assert "ERP" in names, names


# --- Generate control ---
def test_stop_no_active_run():
    assert S.post(f"{API}/generate/stop", timeout=30).status_code == 400


def test_generate_validation():
    assert S.post(f"{API}/generate", json={"scale": 2}, timeout=30).status_code == 422
    assert S.post(f"{API}/generate", json={"n_docs": 10}, timeout=30).status_code == 422


def test_generate_resume_then_409():
    r = S.post(f"{API}/generate", json={"seed": 42, "scale": 0.1, "n_docs": 3000, "fresh": False}, timeout=30)
    assert r.status_code == 200 and r.json()["pid"]
    time.sleep(1.5)
    r2 = S.post(f"{API}/generate", json={"seed": 42, "scale": 0.1, "n_docs": 3000, "fresh": False}, timeout=30)
    st = S.get(f"{API}/status", timeout=30).json()["status"]["state"]
    # 409 only if still running
    if st == "running":
        assert r2.status_code == 409
    for _ in range(60):
        st = S.get(f"{API}/status", timeout=30).json()
        if st["status"]["state"] == "completed":
            break
        time.sleep(2)
    assert st["status"]["state"] == "completed"
    assert all(b["status"] == "completed" for b in st["batches"])
    print("409 observed:", r2.status_code)


# --- Export ---
def test_export_flow():
    r = S.post(f"{API}/export", params={"include_ground_truth": "false"}, timeout=30)
    assert r.status_code == 200 and r.json()["state"] == "building"
    assert S.post(f"{API}/export", timeout=30).status_code == 409
    for _ in range(100):
        e = S.get(f"{API}/export/status", timeout=30).json()
        if e["state"] != "building":
            break
        time.sleep(3)
    assert e["state"] == "ready", e
    assert "ground_truth" not in e["file"]
    r = S.get(f"{API}/export/download", stream=True, timeout=120)
    assert r.status_code == 200 and "application/zip" in r.headers["content-type"]
    assert next(r.iter_content(4)) == b"PK\x03\x04"
    r.close()
