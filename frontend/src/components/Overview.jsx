import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid, LineChart, Line } from "recharts";
import { http, fmt } from "../lib/api";
import { Panel, Stat, DataTable, Empty } from "./common";

const tip = { contentStyle: { background: "#1E2533", border: "1px solid #3E4C66", fontFamily: "JetBrains Mono", fontSize: 12 }, labelStyle: { color: "#F8FAFC" } };
const kt = (v) => `${(v / 1000).toFixed(0)}k`;

export default function Overview({ status }) {
  const [g, setG] = useState(null);
  const [v, setV] = useState(null);
  const [idx, setIdx] = useState(null);
  useEffect(() => {
    http.get("/ghg/summary").then((r) => setG(r.data)).catch(() => setG(null));
    http.get("/validation").then((r) => setV(r.data)).catch(() => {});
    http.get("/index").then((r) => setIdx(r.data)).catch(() => {});
  }, [status?.state]);
  const s = v?.summary;
  const totalRows = idx?.datasets?.reduce((a, d) => a + d.rows, 0);
  return (
    <div className="space-y-6" data-testid="overview-page">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <Stat testid="stat-datasets" label="Datasets" value={fmt(idx?.datasets?.length)} sub="interlinked tables" />
        <Stat testid="stat-records" label="Records" value={totalRows ? `${(totalRows / 1e6).toFixed(2)}M` : "—"} sub="across all systems" accent="text-cyan-400" />
        <Stat testid="stat-anomalies" label="Labelled anomalies" value={fmt(s?.ground_truth_anomalies)} sub="hidden ground truth" accent="text-amber-400" />
        <Stat testid="stat-pass" label="Validation pass" value={s ? `${s.enterprise_pass_pct}%` : "—"} sub={s?.overall_status} />
        <Stat testid="stat-status" label="Engine" value={(status?.state || "idle").toUpperCase()} sub={status?.current_batch || "—"} accent="text-slate-100" />
      </div>
      {!g ? <Empty /> : (
        <>
          <div className="grid lg:grid-cols-5 gap-6">
            <Panel testid="chart-scope12" className="lg:col-span-3" eyebrow="GHG Protocol · operational control" title="Scope 1 & 2 trajectory (tCO2e)">
              <div className="h-72">
                <ResponsiveContainer>
                  <BarChart data={g.trend}>
                    <CartesianGrid stroke="#2A3447" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="year" stroke="#64748B" fontSize={12} />
                    <YAxis stroke="#64748B" fontSize={11} tickFormatter={kt} />
                    <Tooltip {...tip} formatter={(x) => fmt(x)} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="scope1" name="Scope 1" fill="#10B981" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="scope2_location" name="Scope 2 location" fill="#F59E0B" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="scope2_market" name="Scope 2 market" fill="#06B6D4" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
            <Panel testid="chart-scope3" className="lg:col-span-2" eyebrow="Value chain" title="Scope 3 total (tCO2e)">
              <div className="h-72">
                <ResponsiveContainer>
                  <LineChart data={g.trend}>
                    <CartesianGrid stroke="#2A3447" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="year" stroke="#64748B" fontSize={12} />
                    <YAxis stroke="#64748B" fontSize={11} tickFormatter={(v) => `${(v / 1e6).toFixed(1)}M`} />
                    <Tooltip {...tip} formatter={(x) => fmt(x)} />
                    <Line dataKey="scope3" name="Scope 3" stroke="#8B5CF6" strokeWidth={2.5} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </div>
          <Panel testid="chart-scope3-categories" eyebrow="All 15 categories · 2022-2026 cumulative" title="Scope 3 by category (tCO2e, log scale)">
            <div className="h-72">
              <ResponsiveContainer>
                <BarChart data={g.scope3_categories}>
                  <CartesianGrid stroke="#2A3447" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="category_id" stroke="#64748B" fontSize={11} />
                  <YAxis scale="log" domain={[1, "auto"]} allowDataOverflow stroke="#64748B" fontSize={11} tickFormatter={(v) => (v >= 1e6 ? `${v / 1e6}M` : v >= 1e3 ? `${v / 1e3}k` : v)} />
                  <Tooltip {...tip} formatter={(x) => fmt(x)} />
                  <Bar dataKey="tco2e" fill="#8B5CF6" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <div className="grid lg:grid-cols-2 gap-6">
            <Panel testid="neutralisation-ledger" eyebrow="Credits never reduce the inventory" title="Residual emissions & neutralisation ledger">
              <DataTable max="max-h-72" rows={g.ledger} cols={["reporting_year", "residual_scope12_tco2e", "credits_retired_t", "removal_credits_retired_t", "avoidance_credits_retired_t", "remaining_neutralisation_requirement_tco2e"]} />
            </Panel>
            <Panel testid="decarb-table" eyebrow="Base scenario · interaction-adjusted" title="Decarbonisation levers">
              <DataTable max="max-h-72" rows={g.decarbonisation.map((d) => ({ lever: d.opportunity_name, sites: d.n, reduction_t: fmt(d.reduction), capex_usd: fmt(d.capex), savings_usd_yr: fmt(d.savings) }))} />
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
