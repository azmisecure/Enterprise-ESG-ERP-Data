import { useEffect, useState } from "react";
import { Lock, ShieldAlert } from "lucide-react";
import { Switch } from "./ui/switch";
import { Button } from "./ui/button";
import { http, fmt } from "../lib/api";
import { Panel, Tag, DataTable, Empty } from "./common";

const SEV = { Critical: "FAIL", High: "FAIL", Medium: "WARN", Low: "INFO" };

export default function GroundTruth({ status }) {
  const [sum, setSum] = useState(null);
  const [clear, setClear] = useState(false);
  const [f, setF] = useState({ family: "", split: "", severity: "", search: "" });
  const [page, setPage] = useState(1);
  const [res, setRes] = useState(null);
  useEffect(() => { http.get("/anomalies/summary").then((r) => setSum(r.data)).catch(() => setSum(null)); }, [status?.state]);
  useEffect(() => {
    if (!clear) { setRes(null); return; }
    let live = true;
    const t = setTimeout(() => http.get("/anomalies", { params: { clearance: true, ...f, page } }).then((r) => live && setRes(r.data)), 300);
    return () => { live = false; clearTimeout(t); };
  }, [clear, f, page]);
  if (!sum) return <Empty text="Ground truth is assembled in batch B14." />;
  const sel = (k, opts) => (
    <select data-testid={`gt-filter-${k}`} value={f[k]} onChange={(e) => { setPage(1); setF({ ...f, [k]: e.target.value }); }} className="bg-[#11151C] border border-[#2A3447] rounded px-2 py-1.5 text-xs font-mono text-slate-200">
      <option value="">all {k}</option>{opts.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
  return (
    <div className="space-y-6" data-testid="ground-truth-page">
      <div className="grid lg:grid-cols-3 gap-6">
        <Panel eyebrow="Restricted dataset" title={`${fmt(sum.total)} labelled anomalies`} testid="gt-summary"
          right={<div className="flex items-center gap-2"><span className="text-xs text-slate-400">View ground truth</span><Switch data-testid="clearance-switch" checked={clear} onCheckedChange={setClear} /></div>}>
          <div className="space-y-2">
            {Object.entries(sum.by_split).map(([k, v]) => <div key={k} className="flex justify-between font-mono text-sm" data-testid={`split-${k}`}><span className="text-slate-400">{k}</span><span className="text-emerald-300">{fmt(v)}</span></div>)}
            <div className="border-t border-[#2A3447] pt-2 flex flex-wrap gap-2">{Object.entries(sum.by_severity).map(([k, v]) => <Tag key={k} tone={SEV[k] || "MUTED"}>{k} {fmt(v)}</Tag>)}</div>
          </div>
        </Panel>
        <Panel className="lg:col-span-2" eyebrow="By family" title="Anomaly taxonomy" testid="gt-taxonomy">
          <div className="grid sm:grid-cols-3 gap-3">
            {Object.entries(sum.by_family).map(([k, v]) => <div key={k} className="p-3 rounded border border-[#2A3447]"><div className="font-mono text-[11px] text-slate-400">{k.replaceAll("_", " ")}</div><div className="font-display text-2xl font-bold text-amber-400">{fmt(v)}</div></div>)}
          </div>
        </Panel>
      </div>
      {!clear ? (
        <div className="panel p-10 text-center" data-testid="gt-locked"><Lock className="w-8 h-8 mx-auto text-slate-500 mb-3" /><div className="text-slate-300">Labels are hidden from raw datasets and locked here by default.</div><div className="text-slate-500 text-sm mt-1">Enable "View ground truth" to inspect expected vs. actual values and corrections.</div></div>
      ) : (
        <Panel eyebrow={<span className="flex items-center gap-1"><ShieldAlert className="w-3 h-3" /> ground-truth clearance active</span>} title={`${fmt(res?.total)} matching anomalies`} testid="gt-table-panel"
          right={<div className="flex flex-wrap gap-2">{sel("family", Object.keys(sum.by_family))}{sel("split", Object.keys(sum.by_split))}{sel("severity", Object.keys(sum.by_severity))}
            <input data-testid="gt-search" placeholder="subtype / record id" value={f.search} onChange={(e) => { setPage(1); setF({ ...f, search: e.target.value }); }} className="bg-[#11151C] border border-[#2A3447] rounded px-2 py-1.5 text-xs font-mono" /></div>}>
          <DataTable testid="gt-table" rows={res?.rows || []} cols={["anomaly_id", "evaluation_split", "severity", "family", "anomaly_subtype", "source_dataset", "source_record_id", "expected_value", "actual_value", "root_cause", "detection_method", "recommended_correction", "affected_emissions_category"]} />
          <div className="flex justify-end gap-2 mt-3">
            <Button data-testid="gt-prev" variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Prev</Button>
            <span className="font-mono text-xs text-slate-400 self-center">page {page}</span>
            <Button data-testid="gt-next" variant="outline" size="sm" disabled={!res || page * 50 >= res.total} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </Panel>
      )}
    </div>
  );
}
