export const Panel = ({ title, eyebrow, right, children, className = "", testid }) => (
  <section data-testid={testid} className={`panel p-5 fade-up ${className}`}>
    {(title || eyebrow) && (
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
          {title && <h3 className="font-display text-xl font-semibold text-slate-100">{title}</h3>}
        </div>
        {right}
      </div>
    )}
    {children}
  </section>
);

export const Stat = ({ label, value, sub, accent = "text-emerald-400", testid }) => (
  <div data-testid={testid} className="panel p-4 fade-up">
    <div className="eyebrow !text-slate-400">{label}</div>
    <div className={`font-display text-3xl font-bold mt-1 ${accent}`}>{value}</div>
    {sub && <div className="text-xs text-slate-500 mt-1 font-mono">{sub}</div>}
  </div>
);

const TONE = { PASS: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30", WARN: "bg-amber-500/15 text-amber-300 border-amber-500/30", FAIL: "bg-rose-500/15 text-rose-300 border-rose-500/30", INFO: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30", MUTED: "bg-slate-500/10 text-slate-400 border-slate-500/30" };
export const Tag = ({ tone = "MUTED", children, testid }) => (
  <span data-testid={testid} className={`inline-flex items-center px-2 py-0.5 rounded border text-[10px] font-mono uppercase tracking-wider ${TONE[tone]}`}>{children}</span>
);
export const toneFor = (s = "") => (s.startsWith("FAIL") || s === "failed" ? "FAIL" : s.includes("WARN") || s === "running" || s === "Partial" ? "WARN" : s.startsWith("PASS") || s === "completed" || s === "Complete" || s === "VALIDATED" ? "PASS" : "MUTED");

export const DataTable = ({ rows, cols, testid, max = "max-h-[460px]", onRow }) => {
  const c = cols || (rows[0] ? Object.keys(rows[0]) : []);
  return (
    <div className={`overflow-auto scroll-thin border border-[#2A3447] rounded-md ${max}`} data-testid={testid}>
      <table className="dense w-full">
        <thead><tr>{c.map((k) => <th key={k}>{k}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} onClick={() => onRow && onRow(r)} className={onRow ? "cursor-pointer" : ""}>
              {c.map((k) => <td key={k} title={String(r[k] ?? "")}>{r[k] === null || r[k] === undefined ? <span className="text-slate-600">null</span> : typeof r[k] === "object" ? JSON.stringify(r[k]) : String(r[k])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <div className="p-6 text-center text-slate-500 text-sm">No rows yet — run a generation batch first.</div>}
    </div>
  );
};

export const Empty = ({ text = "Nothing generated yet. Start a run from the Generator tab." }) => <div className="panel p-10 text-center text-slate-400" data-testid="empty-state">{text}</div>;
