import { useEffect, useState } from "react";
import { FileText, FileSpreadsheet, Mail, FileCode2, Download, Archive, FolderTree } from "lucide-react";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Progress } from "./ui/progress";
import { http, fmt, bytes, fileUrl, API } from "../lib/api";
import { Panel, Tag, Empty } from "./common";

const ICON = { pdf: FileText, docx: FileText, xlsx: FileSpreadsheet, eml: Mail };

export function Documents({ status }) {
  const [t, setT] = useState(""); const [f, setF] = useState(""); const [page, setPage] = useState(1); const [d, setD] = useState(null);
  useEffect(() => { http.get("/documents", { params: { doc_type: t, fmt: f, page } }).then((r) => setD(r.data)); }, [t, f, page, status?.state]);
  if (!d?.total && !t && !f) return <Empty text="Documents are produced in batch B13." />;
  return (
    <Panel eyebrow="Actual files · linked to source records" title={`${fmt(d?.total)} synthetic business documents`} testid="documents-page"
      right={<div className="flex gap-2">
        <select data-testid="doc-type-filter" value={t} onChange={(e) => { setPage(1); setT(e.target.value); }} className="bg-[#11151C] border border-[#2A3447] rounded px-2 py-1.5 text-xs font-mono"><option value="">all types</option>{d?.types.map((x) => <option key={x}>{x}</option>)}</select>
        <select data-testid="doc-format-filter" value={f} onChange={(e) => { setPage(1); setF(e.target.value); }} className="bg-[#11151C] border border-[#2A3447] rounded px-2 py-1.5 text-xs font-mono"><option value="">all formats</option>{d?.formats.map((x) => <option key={x}>{x}</option>)}</select>
      </div>}>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {d?.rows.map((r) => { const I = ICON[r.file_format] || FileCode2; return (
          <a key={r.document_id} href={fileUrl(r.path)} data-testid={`doc-card-${r.document_id}`} className="group p-3 rounded border border-[#2A3447] hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-colors">
            <div className="flex items-center gap-2"><I className="w-4 h-4 text-cyan-400" /><span className="font-mono text-[11px] text-slate-400">{r.document_id}</span><Tag tone="INFO">{r.file_format}</Tag><Download className="w-3.5 h-3.5 ml-auto text-slate-600 group-hover:text-emerald-400" /></div>
            <div className="text-sm text-slate-200 mt-2 truncate" title={r.title}>{r.title}</div>
            <div className="text-[11px] text-slate-500 font-mono mt-1 truncate">{r.document_type} · {r.related_dataset || "—"} · {r.related_record_id || ""}</div>
          </a>); })}
      </div>
      {d && !d.total && <div data-testid="doc-no-match" className="p-8 text-center text-slate-500 text-sm">No documents match this type and format combination.</div>}
      <div className="flex justify-end gap-2 mt-4">
        <Button data-testid="doc-prev" variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Prev</Button>
        <span className="font-mono text-xs text-slate-400 self-center">page {page}</span>
        <Button data-testid="doc-next" variant="outline" size="sm" disabled={!d || page * 48 >= d.total} onClick={() => setPage(page + 1)}>Next</Button>
      </div>
    </Panel>
  );
}

export function Export({ status }) {
  const [tree, setTree] = useState([]); const [ex, setEx] = useState({ state: "idle" });
  useEffect(() => { http.get("/tree").then((r) => setTree(r.data)); http.get("/export/status").then((r) => setEx(r.data)); }, [status?.state]);
  useEffect(() => {
    if (ex.state !== "building") return;
    const i = setInterval(() => http.get("/export/status").then((r) => setEx(r.data)), 1500);
    return () => clearInterval(i);
  }, [ex.state]);
  const build = async (gt) => { try { const r = await http.post(`/export?include_ground_truth=${gt}`); setEx(r.data); toast("Packaging ZIP…"); } catch (e) { toast.error(e.response?.data?.detail || "Export failed"); } };
  return (
    <div className="grid xl:grid-cols-5 gap-6" data-testid="export-page">
      <Panel className="xl:col-span-2" eyebrow="Enterprise_ESG_Synthetic_Data/" title="Download full dataset" testid="export-panel">
        <div className="space-y-3">
          <Button data-testid="export-raw-btn" disabled={ex.state === "building"} onClick={() => build(false)} className="w-full bg-emerald-500 hover:bg-emerald-400 text-black font-semibold"><Archive className="w-4 h-4 mr-2" />Build ZIP (raw data, labels excluded)</Button>
          <Button data-testid="export-gt-btn" disabled={ex.state === "building"} onClick={() => build(true)} variant="outline" className="w-full border-amber-500/40 text-amber-300"><Archive className="w-4 h-4 mr-2" />Build ZIP incl. restricted ground truth</Button>
          {ex.state === "building" && <div data-testid="export-progress"><Progress value={ex.total ? (100 * ex.done) / ex.total : 2} /><div className="text-xs font-mono text-slate-400 mt-1">{fmt(ex.done)} / {fmt(ex.total)} files</div></div>}
          {ex.state === "ready" && <a data-testid="export-download-link" href={`${API}/export/download`} className="flex items-center justify-center gap-2 w-full py-2 rounded border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10"><Download className="w-4 h-4" />{ex.file} · {bytes(ex.size_bytes)}</a>}
          {ex.state === "failed" && <div className="text-rose-400 text-sm">{ex.error}</div>}
          <p className="text-xs text-slate-500">Files also live on the server under /app/data/Enterprise_ESG_Synthetic_Data for direct pipeline ingestion.</p>
        </div>
      </Panel>
      <Panel className="xl:col-span-3" eyebrow="Output directory" title="Folder structure" testid="folder-tree-panel" right={<FolderTree className="w-5 h-5 text-slate-500" />}>
        <div className="space-y-2 max-h-[600px] overflow-auto scroll-thin">
          {tree.map((n) => (
            <div key={n.name} className="p-2 rounded border border-[#2A3447]" data-testid={`folder-${n.name}`}>
              <div className="flex items-center gap-2"><span className="font-mono text-sm text-emerald-300">{n.name}/</span><span className="text-[11px] font-mono text-slate-500 ml-auto">{fmt(n.files)} files · {bytes(n.size_bytes)}</span></div>
              <div className="flex flex-wrap gap-1 mt-1">{Object.entries(n.extensions).map(([e, c]) => <Tag key={e}>{e} {c}</Tag>)}</div>
              {n.subfolders.length > 0 && <div className="text-[11px] font-mono text-slate-500 mt-1 truncate" title={n.subfolders.join(", ")}>└ {n.subfolders.join(" · ")}</div>}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
