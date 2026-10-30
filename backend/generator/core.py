import json, zlib, hashlib, time
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd

START = pd.Timestamp("2022-01-01")
END = pd.Timestamp("2026-12-31")
YEARS = [2022, 2023, 2024, 2025, 2026]
DAYS = pd.date_range(START, END, freq="D")
MONTHS = pd.period_range("2022-01", "2026-12", freq="M")
SCHEMA_VERSION = "4.2.0"
TRANSFORM_VERSION = "tx-1.3.0"
ENTERPRISE_ID = "ENT-0001"
SEASON = np.array([0.92, 0.95, 1.04, 1.03, 1.05, 1.02, 0.94, 0.86, 1.04, 1.07, 1.05, 0.93])
WEEKDAY = np.array([1.0, 1.02, 1.03, 1.01, 0.96, 0.22, 0.08])
GROWTH = {2022: 1.0, 2023: 1.07, 2024: 1.04, 2025: 1.11, 2026: 1.16}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def zipf(n, a=1.1):
    w = 1.0 / np.arange(1, n + 1) ** a
    return w / w.sum()


def ids(prefix, n, width=6, start=1):
    return np.char.add(prefix, np.char.zfill(np.arange(start, start + n).astype(str), width))


def day_weights(business=True):
    w = SEASON[DAYS.month - 1] * np.array([GROWTH[y] for y in DAYS.year])
    if business:
        w = w * WEEKDAY[DAYS.dayofweek]
    return w / w.sum()


def rand_dates(rng, n, business=True):
    return DAYS[rng.choice(len(DAYS), n, p=day_weights(business))]


def fiscal(dates, fy_start):
    d = pd.DatetimeIndex(dates)
    s = np.asarray(fy_start)
    m = d.month.values
    fy = d.year.values + ((s > 1) & (m >= s)).astype(int)
    fp = (m - s) % 12 + 1
    return fy, fp


class Ctx:
    def __init__(self, root, seed=42, scale=0.1, n_docs=3000, log=print):
        self.root = Path(root)
        self.seed, self.scale, self.n_docs, self.log = seed, scale, n_docs, log
        self.cache, self.anoms, self.files = {}, [], []
        self.batch_id = None
        self.reg_path = self.root / "Dataset_Index" / "_registry.json"
        self.registry = json.loads(self.reg_path.read_text()) if self.reg_path.exists() else {}

    def rng(self, key):
        return np.random.default_rng([self.seed, zlib.crc32(key.encode())])

    def n(self, target):
        return max(1, int(round(target * self.scale)))

    def path(self, rel):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def save(self, df, rel, name, pk=None, fks=None, target=None, desc="", system="", domain=""):
        p = self.path(rel)
        ext = p.suffix[1:]
        if ext == "parquet":
            df.to_parquet(p, index=False)
        elif ext == "csv":
            df.to_csv(p, index=False)
        elif ext == "json":
            p.write_text(df.to_json(orient="records", date_format="iso", indent=1))
        elif ext == "jsonl":
            df.to_json(p, orient="records", lines=True, date_format="iso")
        elif ext == "xlsx":
            df.to_excel(p, index=False)
        self.cache[name] = df
        self.registry[name] = dict(
            name=name, path=rel, format=ext, rows=int(len(df)),
            columns=[dict(name=c, dtype=str(t)) for c, t in df.dtypes.items()],
            pk=pk, fks=fks or {}, target=target,
            scaled_target=(self.n(target) if target else None),
            batch_id=self.batch_id, source_system=system, description=desc,
            domain=domain or rel.split("/")[0], created=now_iso(),
            size_bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        )
        self.log(f"GENERATING {name}: {len(df):,} rows -> {rel}")
        return df

    def get(self, name):
        if name not in self.cache:
            meta = self.registry[name]
            p = self.root / meta["path"]
            if meta["format"] == "parquet":
                df = pd.read_parquet(p)
            elif meta["format"] == "json":
                df = pd.read_json(p)
            else:
                df = pd.read_csv(p, low_memory=False)
            for c in meta["columns"]:
                if c["dtype"].startswith("datetime") and c["name"] in df:
                    df[c["name"]] = pd.to_datetime(df[c["name"]])
            self.cache[name] = df
        return self.cache[name]

    def write(self, rel, content, kind="raw", entity=None, period=None, dept=None, system=None, encoding="utf-8"):
        p = self.path(rel)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding=encoding, errors="replace")
        self.files.append(dict(path=rel, kind=kind, entity=entity, period=period, dept=dept, system=system, batch_id=self.batch_id))
        return p

    def track(self, rel, kind="document", entity=None, period=None, dept=None, system=None):
        self.files.append(dict(path=rel, kind=kind, entity=entity, period=period, dept=dept, system=system, batch_id=self.batch_id))

    def anom(self, dataset, ids_, atype, subtype, severity, expected, actual, root_cause, method,
             correction, corrected=None, process="", ghg="", impact=None, related=None,
             family="Data_Inconsistencies", system=""):
        ids_ = np.asarray(ids_, dtype=object)
        n = len(ids_)
        if n == 0:
            return
        b = lambda v: (np.asarray(v, dtype=object) if np.ndim(v) else np.full(n, v, dtype=object))
        self.anoms.append(pd.DataFrame(dict(
            family=family, source_system=system or self.registry.get(dataset, {}).get("source_system", ""),
            source_dataset=dataset, source_record_id=ids_, related_record_ids=b(related if related is not None else ""),
            anomaly_type=atype, anomaly_subtype=subtype, severity=b(severity),
            expected_value=[str(x) for x in b(expected)], actual_value=[str(x) for x in b(actual)],
            root_cause=root_cause, detection_method=method, recommended_correction=correction,
            expected_corrected_value=[str(x) for x in b(corrected if corrected is not None else expected)],
            affected_business_process=process, affected_emissions_category=ghg,
            expected_emissions_impact_kgco2e=b(impact if impact is not None else 0.0),
            injection_version="inj-1.0", batch_id=self.batch_id,
        )))

    def lineage(self, df, system, app, database, table, owner, src_ids, ts_col=None, period_col=None):
        rng = self.rng("lin" + table)
        df["source_system"] = system
        df["source_application"] = app
        df["source_database"] = database
        df["source_table"] = table
        df["source_record_id"] = src_ids
        df["data_owner"] = owner
        if ts_col is not None:
            base = pd.to_datetime(df[ts_col])
            df["source_record_timestamp"] = base + pd.to_timedelta(rng.integers(6, 20, len(df)), "h")
            df["ingestion_timestamp"] = df["source_record_timestamp"] + pd.to_timedelta(rng.gamma(2, 6, len(df)), "h").round("s")
            df["processing_timestamp"] = df["ingestion_timestamp"] + pd.to_timedelta(rng.integers(30, 900, len(df)), "s")
        df["schema_version"] = SCHEMA_VERSION
        df["transformation_version"] = TRANSFORM_VERSION
        return df

    def flush(self):
        self.reg_path.parent.mkdir(parents=True, exist_ok=True)
        self.reg_path.write_text(json.dumps(self.registry, indent=1, default=str))
        bdir = self.root / "Anomaly_Ground_Truth" / "_batches"
        bdir.mkdir(parents=True, exist_ok=True)
        if self.anoms:
            pd.concat(self.anoms, ignore_index=True).to_parquet(bdir / f"{self.batch_id}.parquet", index=False)
        fdir = self.root / "Generation_Configuration" / "_files"
        fdir.mkdir(parents=True, exist_ok=True)
        if self.files:
            pd.DataFrame(self.files).to_parquet(fdir / f"{self.batch_id}.parquet", index=False)
        self.anoms, self.files = [], []

    def start_batch(self, bid):
        self.batch_id = bid
        self.anoms, self.files = [], []
        for d in ["Anomaly_Ground_Truth/_batches", "Generation_Configuration/_files"]:
            f = self.root / d / f"{bid}.parquet"
            if f.exists():
                f.unlink()


def pick_rows(rng, n_total, frac):
    k = int(n_total * frac)
    return np.sort(rng.choice(n_total, k, replace=False)) if k else np.array([], dtype=int)


def timer():
    t = time.time()
    return lambda: round(time.time() - t, 1)
