import { useCallback, useEffect, useState } from "react";
import "@/App.css";
import { LayoutDashboard, Cpu, Database, ShieldCheck, EyeOff, FileStack, Archive } from "lucide-react";
import { Toaster } from "./components/ui/sonner";
import { http } from "./lib/api";
import Overview from "./components/Overview";
import Generate from "./components/Generate";
import Datasets from "./components/Datasets";
import Validation from "./components/Validation";
import GroundTruth from "./components/GroundTruth";
import { Documents, Export } from "./components/Files";
import { Tag, toneFor } from "./components/common";

const NAV = [["overview", "Overview", LayoutDashboard], ["generate", "Generator", Cpu], ["datasets", "Datasets", Database], ["validation", "Validation", ShieldCheck],
  ["ground-truth", "Ground truth", EyeOff], ["documents", "Documents", FileStack], ["export", "Export", Archive]];

function App() {
  const [tab, setTab] = useState("overview");
  const [data, setData] = useState(null);
  const refresh = useCallback(() => http.get("/status").then((r) => setData(r.data)).catch(() => {}), []);
  useEffect(() => { refresh(); const i = setInterval(refresh, 2500); return () => clearInterval(i); }, [refresh]);
  const st = data?.status || {};
  const props = { status: st, data, refresh };
  return (
    <div className="min-h-screen grid-bg noise">
      <header className="sticky top-0 z-50 bg-[#090B0E]/85 backdrop-blur-md border-b border-[#2A3447]">
        <div className="max-w-[1500px] mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center gap-4">
          <div>
            <div className="eyebrow">Synthetic enterprise data engine</div>
            <h1 className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight leading-none">HALVORSEN-KAITO <span className="text-emerald-400">// ESG DATA FORGE</span></h1>
          </div>
          <div className="ml-auto flex items-center gap-3 font-mono text-xs" data-testid="header-status">
            <span className={`w-2 h-2 rounded-full ${st.state === "running" ? "bg-amber-400 pulse-dot" : st.state === "completed" ? "bg-emerald-400" : "bg-slate-500"}`} />
            <Tag tone={toneFor(st.state)} testid="engine-state">{st.state || "idle"}</Tag>
            {st.current_batch && st.state === "running" && <span className="text-amber-300" data-testid="active-batch">{st.current_batch} · {st.progress}%</span>}
            {data?.config && <span className="text-slate-400 hidden md:inline">seed {data.config.seed} · scale {data.config.scale} · docs {data.config.n_docs}</span>}
          </div>
        </div>
        <nav className="max-w-[1500px] mx-auto px-4 sm:px-6 flex gap-1 overflow-x-auto scroll-thin">
          {NAV.map(([k, l, I]) => (
            <button key={k} data-testid={`nav-${k}`} onClick={() => setTab(k)} className={`flex items-center gap-2 px-3 py-2 text-sm border-b-2 whitespace-nowrap transition-colors ${tab === k ? "border-emerald-400 text-emerald-300" : "border-transparent text-slate-400 hover:text-slate-200"}`}>
              <I className="w-4 h-4" />{l}
            </button>
          ))}
        </nav>
      </header>
      <main className="max-w-[1500px] mx-auto px-4 sm:px-6 py-8" key={tab}>
        {tab === "overview" && <Overview {...props} />}
        {tab === "generate" && <Generate {...props} />}
        {tab === "datasets" && <Datasets {...props} />}
        {tab === "validation" && <Validation {...props} />}
        {tab === "ground-truth" && <GroundTruth {...props} />}
        {tab === "documents" && <Documents {...props} />}
        {tab === "export" && <Export {...props} />}
        <footer className="mt-12 text-[11px] font-mono text-slate-600">All organisations, records, emission factors, documents and certificates are SYNTHETIC and for testing only.</footer>
      </main>
      <Toaster theme="dark" position="bottom-right" />
    </div>
  );
}

export default App;
