import { useHealth } from "../../api/queries.ts";
import { Panel } from "../../components/Panel.tsx";
import { StatusDot } from "../../components/console/atoms.tsx";
import { Notice } from "../../components/console/fields.tsx";
import { formatApiError } from "../../lib/errors.ts";
import { formatHealthStatus, formatTimestamp } from "../../lib/format.ts";

export function HealthPanel() {
  const health = useHealth();
  const lastChecked = health.data?.reduce<string | null>((latest, check) => {
    if (latest === null) return check.timestamp;
    return new Date(check.timestamp) > new Date(latest) ? check.timestamp : latest;
  }, null);

  return (
    <Panel title="Health">
      {health.isLoading && <p className="text-xs text-slate-600">loading…</p>}
      {health.error !== null && <Notice tone="error">{formatApiError(health.error)}</Notice>}
      <ul className="space-y-1.5 text-sm">
        {health.data?.map((check) => (
          <li key={check.service_name} className="flex items-center gap-2">
            <StatusDot status={check.is_healthy ? "succeeded" : "failed"} />
            <span>{check.service_name}</span>
            <span
              className={`ml-auto text-[11px] ${check.is_healthy ? "text-emerald-400" : "text-rose-400"}`}
            >
              {formatHealthStatus(check.is_healthy)}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] text-slate-600">
        last checked {formatTimestamp(lastChecked ?? null)}
      </p>
    </Panel>
  );
}
