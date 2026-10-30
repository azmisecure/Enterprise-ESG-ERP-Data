import { useEffect, useMemo, useState } from "react";
import { Search, Download } from "lucide-react";
import { Input } from "./ui/input";
import { http, fmt, bytes, fileUrl } from "../lib/api";
import { Panel, Tag, toneFor, DataTable, Empty } from "./common";

export default function Datasets({ status }) {
  const [idx, setIdx] = useState(null);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(null);
  const [pv, setPv] = useState(null);
  const [row, setRow] = useState(null);
  useEffect(() => { http.get("/index").then((r) => setIdx(r.data)); }, [status?.state]);
  useEffect(() => { if (sel) { setPv(null); setRow(null); http.get(`/datasets/${sel}/preview?limit=100`).then((r) => setPv(r.data)); } }, [sel]);
  const groups = useMemo(() => {
    const g = {};
    (idx?.datasets || []).filter((d) => d.name.includes(q.toLowerCase()) || d.path.toLowerCase().includes(q.toLowerCase())).forEach((d) => { (g[d.domain] = g[d.domain] || []).push(d); });
    return g;
  }, [idx, q]);
  if (!idx?.datasets?.length) return <Empty />;
  return (
    <div className="space-y-6" data-testid="datasets-page">
      <div className="grid xl:grid-cols-3 gap-6">
        <Panel eyebrow={`${idx.datasets.length} datasets`} title="Dataset index" testid="dataset-tree">
          <div className="relative mb-3"><Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" /><Input data-testid="dataset-search" placeholder="filter tables…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9 bg-[#11151C] font-mono text-sm" /></div>
          <div className="max-h-[620px] overflow-auto scroll-thin space-y-4 pr-1">
            {Object.entries(groups).map(([dom, ds]) => (
              <div key={dom}>
                <div className="eyebrow mb-1">{dom}</div>
                {ds.map((d) => (
                  <button key={d.name} data-testid={`dataset-item-${d.name}`} onClick={() => setSel(d.name)} className={`w-full text-left px-2 py-1.5 rounded flex items-center gap-2 transition-colors ${sel === d.name ? "bg-emerald-500/10 border border-emerald-500/30" : "hover:bg-[#1E2533] border border-transparent"}`}>
                    <span className="font-mono text-xs text-slate-200 flex-1 truncate">{d.name}</span>
                    <span className="font-mono text-[10px] text-slate-500">{fmt(d.rows)}</span>
                    <Tag tone="INFO">{d.format}</Tag>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </Panel>
        <Panel className="xl:col-span-2" eyebrow={pv ? `${pv.meta.source_system} · ${pv.meta.batch_id} · pk ${pv.meta.pk || "—"}` : "Select a dataset"} title={sel || "Data preview"} testid="dataset-preview"
          right={pv && <a data-testid="dataset-download-link" href={fileUrl(pv.meta.path)} className="text-xs font-mono text-cyan-300 hover:text-cyan-200 flex items-center gap-1"><Download className="w-3.5 h-3.5" />{pv.meta.path.split("/").pop()}</a>}>
          {pv ? (
            <>
              <div className="flex flex-wrap gap-2 mb-3">
                <Tag tone="PASS">{fmt(pv.meta.rows)} rows</Tag><Tag>{pv.meta.columns.length} columns</Tag>
                {Object.entries(pv.meta.fks || {}).map(([c, r]) => <Tag key={c} tone="WARN">FK {c} → {r}</Tag>)}
              </div>
              <DataTable testid="preview-table" rows={pv.rows} onRow={setRow} />
              {row && <pre data-testid="row-detail" className="mt-3 max-h-64 overflow-auto scroll-thin text-[11px] font-mono bg-[#07090C] border border-[#2A3447] rounded p-3 text-slate-300">{JSON.stringify(row, null, 2)}</pre>}
            </>
          ) : <div className="text-slate-500 text-sm">Pick a table on the left to inspect its first rows, keys and relationships. Click a row for its full record.</div>}
        </Panel>
      </div>
      <Panel eyebrow="Never silently reduced" title="Volume report vs. targets" testid="volume-report">
        <DataTable rows={idx.volume.map((v) => ({ group: v.dataset_group, full_target: fmt(v.full_target), run_target: fmt(v.run_target), generated: fmt(v.generated), outstanding_full: fmt(v.outstanding_vs_full_target), status: v.status, reason: v.reason }))} />
      </Panel>
      <div className="text-xs text-slate-500 font-mono">Total on disk: {bytes(idx.datasets.reduce((a, d) => a + d.size_bytes, 0))} in indexed tables</div>
    </div>
  );
}
