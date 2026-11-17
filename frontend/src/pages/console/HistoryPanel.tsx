import { useState } from "react";
import { useNotification, useNotifications, useRetryDelivery } from "../../api/queries.ts";
import type { Channel, DeliveryResponse, NotificationStatus } from "../../api/types.ts";
import { Panel } from "../../components/Panel.tsx";
import { ChannelTag, StatusChip, StatusDot } from "../../components/console/atoms.tsx";
import { Notice } from "../../components/console/fields.tsx";
import { formatApiError } from "../../lib/errors.ts";
import { formatStatus, formatTimeAgo, formatTimestamp } from "../../lib/format.ts";
import {
  HISTORY_PAGE_SIZE,
  type HistoryFilters,
  canRetry,
  defaultHistoryFilters,
  pageCount,
} from "../../lib/history.ts";

const CHANNEL_FILTERS: (Channel | "all")[] = ["all", "email", "push", "sms", "voice"];
const STATUS_FILTERS: (NotificationStatus | "all")[] = ["all", "pending", "succeeded", "failed"];

const filterClass = (active: boolean) =>
  `rounded px-1.5 py-0.5 text-[11px] ${
    active ? "bg-slate-700 text-slate-100" : "text-slate-500 hover:text-slate-300"
  }`;

export function HistoryPanel() {
  const [filters, setFilters] = useState<HistoryFilters>(defaultHistoryFilters);
  const [offset, setOffset] = useState(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const history = useNotifications(filters, offset);

  const total = history.data?.total ?? 0;
  const pages = pageCount(total, HISTORY_PAGE_SIZE);
  const page = Math.floor(offset / HISTORY_PAGE_SIZE) + 1;

  const applyChannel = (channel: Channel | "all") => {
    setFilters((previous) => ({ ...previous, channel }));
    setOffset(0);
  };
  const applyStatus = (status: NotificationStatus | "all") => {
    setFilters((previous) => ({ ...previous, status }));
    setOffset(0);
  };

  return (
    <Panel title={`History (${total})`}>
      <div className="mb-2 flex flex-wrap items-center gap-1">
        {CHANNEL_FILTERS.map((filter) => (
          <button
            key={filter}
            type="button"
            onClick={() => applyChannel(filter)}
            className={filterClass(filters.channel === filter)}
          >
            {filter}
          </button>
        ))}
        <span className="mx-1 text-slate-700">|</span>
        {STATUS_FILTERS.map((filter) => (
          <button
            key={filter}
            type="button"
            onClick={() => applyStatus(filter)}
            className={filterClass(filters.status === filter)}
          >
            {filter === "all" ? "all" : formatStatus(filter)}
          </button>
        ))}
        <button
          type="button"
          onClick={() => void history.refetch()}
          className="ml-auto rounded px-1.5 py-0.5 text-[11px] text-slate-500 hover:text-slate-300"
        >
          {history.isFetching ? "refreshing…" : "refresh"}
        </button>
      </div>

      {history.isLoading && <p className="py-4 text-center text-xs text-slate-600">loading…</p>}
      {history.error !== null && <Notice tone="error">{formatApiError(history.error)}</Notice>}

      <ul className="space-y-1.5">
        {history.data?.items.map((notification) => {
          const expanded = expandedId === notification.id;
          return (
            <li key={notification.id}>
              <button
                type="button"
                onClick={() => setExpandedId(expanded ? null : notification.id)}
                className="w-full rounded border border-slate-800 bg-slate-900/60 px-2.5 py-2 text-left hover:border-slate-700"
              >
                <div className="flex items-center gap-2">
                  <StatusDot status={notification.status} />
                  <span className="truncate text-sm">{notification.subject ?? "(no subject)"}</span>
                  <span className="ml-auto shrink-0 text-[11px] tabular-nums text-slate-500">
                    {formatTimestamp(notification.created_at)}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-1.5 pl-4">
                  <span className="text-[11px] text-slate-500">
                    {notification.source ?? "no source"}
                  </span>
                  {notification.channels.map((channel) => (
                    <ChannelTag key={channel} channel={channel} />
                  ))}
                  <StatusChip status={notification.status} />
                  <span className="ml-auto text-[11px] text-slate-600">
                    {formatTimeAgo(notification.created_at)}
                  </span>
                </div>
              </button>
              {expanded && <NotificationDetail id={notification.id} />}
            </li>
          );
        })}
      </ul>

      {history.data?.items.length === 0 && (
        <p className="py-6 text-center text-xs text-slate-600">nothing matches</p>
      )}

      <div className="mt-2 flex items-center justify-between border-t border-slate-800 pt-2 text-[11px] text-slate-500">
        <span>
          page {page} of {pages}
        </span>
        <div className="flex gap-1">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset((previous) => Math.max(0, previous - HISTORY_PAGE_SIZE))}
            className="rounded px-1.5 py-0.5 hover:text-slate-300 disabled:opacity-40"
          >
            prev
          </button>
          <button
            type="button"
            disabled={offset + HISTORY_PAGE_SIZE >= total}
            onClick={() => setOffset((previous) => previous + HISTORY_PAGE_SIZE)}
            className="rounded px-1.5 py-0.5 hover:text-slate-300 disabled:opacity-40"
          >
            next
          </button>
        </div>
      </div>
    </Panel>
  );
}

function NotificationDetail({ id }: { id: number }) {
  const detail = useNotification(id);

  if (detail.isLoading) {
    return <p className="mt-1.5 pl-4 text-xs text-slate-600">loading deliveries…</p>;
  }
  if (detail.error !== null) {
    return (
      <div className="mt-1.5 pl-4">
        <Notice tone="error">{formatApiError(detail.error)}</Notice>
      </div>
    );
  }

  return (
    <div className="mt-1.5 space-y-1.5 pl-4">
      {detail.data?.deliveries.map((delivery) => (
        <DeliveryDetail key={delivery.id} delivery={delivery} />
      ))}
    </div>
  );
}

function DeliveryDetail({ delivery }: { delivery: DeliveryResponse }) {
  const retry = useRetryDelivery();
  const retrying = retry.isPending && retry.variables === delivery.id;

  return (
    <div className="rounded border border-slate-800 bg-slate-950/40 px-2.5 py-2">
      <div className="flex items-center gap-2">
        <ChannelTag channel={delivery.channel} />
        <StatusChip status={delivery.status} />
        <span className="truncate text-[11px] text-slate-500">
          {delivery.recipients.length > 0 ? delivery.recipients.join(", ") : "provider default"}
        </span>
        {canRetry(delivery) && (
          <button
            type="button"
            disabled={retrying}
            onClick={() => retry.mutate(delivery.id)}
            className="ml-auto rounded bg-slate-800 px-1.5 py-0.5 text-[11px] text-slate-200 hover:bg-slate-700 disabled:opacity-50"
          >
            {retrying ? "retrying…" : "Retry"}
          </button>
        )}
      </div>

      <p className="mt-1 text-[11px] text-slate-600">options {JSON.stringify(delivery.options)}</p>

      <ul className="mt-1 space-y-0.5">
        {delivery.attempts.map((attempt) => (
          <li
            key={attempt.attempt_number}
            className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500"
          >
            <span className="tabular-nums">#{attempt.attempt_number}</span>
            <span>{attempt.provider}</span>
            <span
              className={attempt.outcome === "succeeded" ? "text-emerald-400" : "text-rose-400"}
            >
              {attempt.outcome}
            </span>
            {attempt.provider_status !== null && (
              <span className="tabular-nums">http {attempt.provider_status}</span>
            )}
            {attempt.error_kind !== null && <span>{attempt.error_kind}</span>}
            {attempt.retriable && <span className="text-amber-400">retriable</span>}
            {attempt.error_message !== null && (
              <span className="w-full truncate text-rose-300">{attempt.error_message}</span>
            )}
            <span className="ml-auto text-slate-600">{formatTimestamp(attempt.started_at)}</span>
          </li>
        ))}
        {delivery.attempts.length === 0 && (
          <li className="text-[11px] text-slate-600">no attempts</li>
        )}
      </ul>

      {retry.error !== null && (
        <div className="mt-1">
          <Notice tone="error">{formatApiError(retry.error)}</Notice>
        </div>
      )}
    </div>
  );
}
