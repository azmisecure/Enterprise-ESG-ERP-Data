import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Play, Pause, RotateCcw } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Slider } from "./ui/slider";
import { Switch } from "./ui/switch";
import { http, fmt } from "../lib/api";
import { Panel, Tag, toneFor } from "./common";

const LEVELS = ["ALL", "INFO", "GENERATING", "WARN", "ERROR", "FK_CHECK"];

export default function Generate({ data, refresh }) {
  const [seed, setSeed] = useState(42);
  const [scale, setScale] = useState(0.1);
  const [docs, setDocs] = useState(3000);
  const [fresh, setFresh] = useState(false);
  const [level, setLevel] = useState("ALL");
  const [auto, setAuto] = useState(true);
  const logRef = useRef(null);
  const st = data?.status || {};
  const running = st.state === "running";
  useEffect(() => { if (data?.config) { setSeed(data.config.seed); setScale(data.config.scale); setDocs(data.config.n_docs); } }, [data?.config?.seed]); // eslint-disable-line
  useEffect(() => { if (auto && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [data?.log, auto]);
  const start = async () => {
    try { await http.post("/generate", { seed: Number(seed), scale, n_docs: Number(docs), fresh }); toast.success(fresh ? "Fresh run started" : "Run started — completed checkpoints are reused"); refresh(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not start run"); }
  };
  const stop = async () => { try { await http.post("/generate/stop"); toast("Paused — resume continues from the last checkpoint"); refresh(); } catch (e) { toast.error(e.response?.data?.detail || "No active run"); } };
  const logs = (data?.log || []).filter((l) => level === "ALL" || l.includes(`[${level}]`));
  const done = (data?.batches || []).filter((b) => b.status === "completed").length;
  return (
    <div className="grid xl:grid-cols-5 gap-6" data-testid="generate-page">
      <div className="xl:col-span-2 space-y-6">
        <Panel eyebrow="Deterministic · resumable" title="Batch run control" testid="batch-control">
          <div className="space-y-5">
            <label className="block"><span className="eyebrow !text-slate-400">Random seed</span>
              <Input data-testid="seed-input" type="number" value={seed} onChange={(e) => setSeed(e.target.value)} className="mt-1 font-mono bg-[#11151C]" /></label>
            <div><div className="flex justify-between"><span className="eyebrow !text-slate-400">Transaction scale</span><span className="font-mono text-emerald-400 text-sm" data-testid="scale-value">{Math.round(scale * 100)}% of targets</span></div>
              <Slider data-testid="scale-slider" className="mt-3" min={0.01} max={1} step={0.01} value={[scale]} onValueChange={(v) => setScale(v[0])} /></div>
            <label className="block"><span className="eyebrow !text-slate-400">Business documents</span>
              <Input data-testid="docs-input" type="number" value={docs} onChange={(e) => setDocs(e.target.value)} className="mt-1 font-mono bg-[#11151C]" /></label>
            <div className="flex items-center justify-between"><span className="text-sm text-slate-300">Discard checkpoints & regenerate</span><Switch data-testid="fresh-switch" checked={fresh} onCheckedChange={setFresh} /></div>
            <div className="flex gap-3">
              <Button data-testid="start-run-btn" disabled={running} onClick={start} className="flex-1 bg-emerald-500 hover:bg-emerald-400 text-black font-semibold">{done && !fresh ? <RotateCcw className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}{done && !fresh ? "Resume / re-run" : "Start generation"}</Button>
              <Button data-testid="pause-run-btn" disabled={!running} onClick={stop} variant="outline" className="border-[#3E4C66]"><Pause className="w-4 h-4 mr-2" />Pause</Button>
            </div>
            <p className="text-xs text-slate-500">Master data (10k suppliers, 20k customers, 75k employees, 10k emission factors) is always full size; transactions scale with the slider. Changing seed or scale starts a new run.</p>
          </div>
        </Panel>
        <Panel eyebrow={`${done}/14 batches complete`} title="Dependency-ordered batches" testid="batch-list">
          <div className="space-y-2">
            {(data?.batches || []).map((b) => (
              <div key={b.batch_id} data-testid={`batch-${b.batch_id}`} className={`flex items-center gap-3 p-2 rounded border ${st.current_batch === b.batch_id && running ? "border-amber-500/50 bg-amber-500/5" : "border-[#2A3447]"}`}>
                <span className="font-mono text-xs text-slate-400 w-8">{b.batch_id}</span>
                <span className="text-sm text-slate-200 flex-1 truncate" title={b.name}>{b.name}</span>
                <span className="font-mono text-[11px] text-slate-500">{b.record_count ? fmt(b.record_count) : ""}</span>
                <Tag tone={toneFor(st.current_batch === b.batch_id && running ? "running" : b.status)}>{st.current_batch === b.batch_id && running ? "running" : b.status || "pending"}</Tag>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel className="xl:col-span-3" eyebrow="Live generation log" title="Engine terminal" testid="log-panel"
        right={<div className="flex items-center gap-2"><span className="text-xs text-slate-400">autoscroll</span><Switch data-testid="autoscroll-switch" checked={auto} onCheckedChange={setAuto} /></div>}>
        <div className="flex flex-wrap gap-2 mb-3">
          {LEVELS.map((l) => <button key={l} data-testid={`log-filter-${l}`} onClick={() => setLevel(l)} className={`px-2 py-1 rounded text-[11px] font-mono border transition-colors ${level === l ? "border-emerald-500 text-emerald-300 bg-emerald-500/10" : "border-[#2A3447] text-slate-400 hover:text-slate-200"}`}>{l}</button>)}
        </div>
        <div ref={logRef} data-testid="log-output" className="h-[640px] overflow-auto scroll-thin bg-[#07090C] border border-[#2A3447] rounded p-3 font-mono text-[11.5px] leading-relaxed">
          {logs.map((l, i) => <div key={i} className={l.includes("[ERROR]") ? "text-rose-400" : l.includes("[WARN]") ? "text-amber-300" : l.includes("[GENERATING]") ? "text-cyan-300" : l.includes("[FK_CHECK]") ? "text-violet-300" : "text-slate-300"}>{l}</div>)}
          {!logs.length && <div className="text-slate-600">Waiting for engine output…</div>}
        </div>
      </Panel>
    </div>
  );
}
