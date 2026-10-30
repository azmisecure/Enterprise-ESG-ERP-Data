import { useEffect, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { http, fmt } from "../lib/api";
import { Panel, Tag, toneFor, DataTable, Empty, Stat } from "./common";

export default function Validation({ status }) {
  const [v, setV] = useState(null);
  useEffect(() => { http.get("/validation").then((r) => setV(r.data)); }, [status?.state]);
  const s = v?.summary;
  if (!s) return <Empty text="Validation runs in batch B14 after all datasets exist." />;
  return (
    <div className="space-y-6" data-testid="validation-page">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <Stat testid="val-overall" label="Overall" value={s.overall_status} accent={s.overall_status === "VALIDATED" ? "text-emerald-400 !text-2xl" : "text-amber-400 !text-2xl"} />
        <Stat label="Pass rate" value={`${s.enterprise_pass_pct}%`} sub="unexplained failures only" />
        <Stat label="Records checked" value={fmt(s.total_records)} accent="text-cyan-400" />
        <Stat label="Injected defects" value={fmt(s.intentionally_defective)} accent="text-amber-400" sub="all labelled" />
        <Stat label="Unexplained" value={fmt(s.unexplained_failures)} accent={s.unexplained_failures ? "text-rose-400" : "text-emerald-400"} sub="natural incompleteness" />
      </div>
      <Panel eyebrow="Mandatory anomaly checks" title="Ground-truth integrity" testid="anomaly-checks">
        <div className="grid md:grid-cols-2 gap-2">
          {Object.entries(s.anomaly_checks).filter(([, x]) => typeof x === "boolean").map(([k, x]) => (
            <div key={k} className="flex items-center gap-2 text-sm text-slate-300">{x ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400" />}{k.replaceAll("_", " ")}</div>
          ))}
        </div>
        <div className="mt-3 text-xs text-slate-500 font-mono">Held-out (test-only) anomaly types: {s.anomaly_checks.holdout_subtypes_only_in_test.join(" · ")}</div>
      </Panel>
      <Panel eyebrow="Structural · referential · business rules" title="Per-dataset validation" testid="dataset-validation-table">
        <DataTable max="max-h-[560px]" rows={v.datasets.map((d) => ({ dataset: d.dataset, batch: d.batch_id, total: fmt(d.total_records), invalid: fmt(d.invalid_records), dup_pk: d.duplicate_pk_records, fk_fail: d.referential_integrity_failures, rule_fail: d.business_rule_failures, injected: fmt(d.intentionally_defective_records), unexplained: d.unexplained_failures, missing_values: fmt(d.missing_values), pass_pct: d.validation_pass_pct, status: d.status }))} />
      </Panel>
    </div>
  );
}
