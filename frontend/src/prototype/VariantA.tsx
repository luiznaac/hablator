// PROTOTYPE — variant A: a dense three-pane console (send | history | health), issue #19.

import { useState } from "react";
import { Panel } from "../components/Panel.tsx";
import { ChannelTag, StatusChip, StatusDot } from "./atoms.tsx";
import { useCompose } from "./compose.ts";
import { ChannelToggle, Field, SubmitNote, TextArea, TextInput } from "./fields.tsx";
import {
  type Channel,
  type Delivery,
  type NotificationStatus,
  channelConfig,
  notificationStatus,
} from "./fixtures.ts";
import { clockTime, timeAgo } from "./format.ts";
import type { PrototypeStore } from "./store.ts";

const CHANNEL_FILTERS: ("all" | Channel)[] = ["all", "email", "push"];
const STATUS_FILTERS: ("all" | NotificationStatus)[] = [
  "all",
  "succeeded",
  "partial",
  "failed",
  "pending",
  "in_progress",
];

function DeliveryDetail({
  delivery,
  onRetry,
}: {
  delivery: Delivery;
  onRetry: (deliveryId: number) => void;
}) {
  const retriableFailure = delivery.attempts.some(
    (attempt) => attempt.status === "failed" && attempt.retriable,
  );
  return (
    <div className="rounded border border-slate-800 bg-slate-950/60 px-2 py-1.5">
      <div className="flex items-center gap-2">
        <ChannelTag channel={delivery.channel} />
        <span className="truncate text-[11px] text-slate-400">{delivery.recipient}</span>
        <span className="ml-auto">
          <StatusChip status={delivery.status} />
        </span>
      </div>
      <ul className="mt-1 space-y-0.5">
        {delivery.attempts.map((attempt) => (
          <li key={attempt.id} className="flex items-start gap-2 text-[11px] text-slate-500">
            <span className="tabular-nums">{clockTime(attempt.attempted_at)}</span>
            <span className={attempt.status === "failed" ? "text-rose-400" : "text-emerald-400"}>
              {attempt.status}
            </span>
            {attempt.error && <span className="text-slate-500">{attempt.error}</span>}
            {attempt.retriable && <span className="text-amber-400">retriable</span>}
          </li>
        ))}
      </ul>
      {retriableFailure && (
        <button
          type="button"
          onClick={() => onRetry(delivery.id)}
          className="mt-1 rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-200 hover:bg-slate-700"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function VariantA({ store }: { store: PrototypeStore }) {
  const compose = useCompose(store);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [channelFilter, setChannelFilter] = useState<"all" | Channel>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | NotificationStatus>("all");

  const visible = store.notifications.filter((notification) => {
    const channelMatches =
      channelFilter === "all" ||
      notification.deliveries.some((delivery) => delivery.channel === channelFilter);
    const statusMatches =
      statusFilter === "all" || notificationStatus(notification) === statusFilter;
    return channelMatches && statusMatches;
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-slate-800 bg-slate-950/90 px-4 py-2.5 backdrop-blur">
        <span className="text-sm font-semibold">hablator</span>
        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
          debug console
        </span>
        <div className="ml-auto flex items-center gap-4 text-[11px] text-slate-400">
          {store.health.map((check) => (
            <span key={check.service_name} className="flex items-center gap-1.5">
              <StatusDot status={check.is_healthy ? "succeeded" : "failed"} />
              {check.service_name}
            </span>
          ))}
        </div>
      </header>

      <main className="grid grid-cols-12 gap-3 p-3">
        <div className="col-span-12 lg:col-span-3">
          <Panel title="Send">
            <form
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                void compose.submit();
              }}
            >
              <Field label="source">
                <TextInput
                  value={compose.form.source}
                  onChange={(source) => compose.update({ source })}
                />
              </Field>
              <Field label="subject">
                <TextInput
                  value={compose.form.subject}
                  onChange={(subject) => compose.update({ subject })}
                  placeholder="What happened?"
                />
              </Field>
              <Field label="body">
                <TextArea
                  value={compose.form.body}
                  onChange={(body) => compose.update({ body })}
                  rows={4}
                  placeholder="Plain-text body"
                />
              </Field>
              <div className="flex gap-1.5">
                <ChannelToggle
                  checked={compose.form.email}
                  onChange={(email) => compose.update({ email })}
                  label="email"
                />
                <ChannelToggle
                  checked={compose.form.push}
                  onChange={(push) => compose.update({ push })}
                  label="push"
                />
              </div>
              {compose.form.email && (
                <Field label="email recipient">
                  <TextInput
                    value={compose.form.emailRecipient}
                    onChange={(emailRecipient) => compose.update({ emailRecipient })}
                  />
                </Field>
              )}
              {compose.form.push && (
                <Field label="push topic">
                  <TextInput
                    value={compose.form.pushRecipient}
                    onChange={(pushRecipient) => compose.update({ pushRecipient })}
                  />
                </Field>
              )}
              <button
                type="button"
                onClick={() => compose.update({ advanced: !compose.form.advanced })}
                className="text-[11px] text-slate-500 hover:text-slate-300"
              >
                {compose.form.advanced ? "− hide advanced" : "+ advanced"}
              </button>
              {compose.form.advanced && (
                <div className="space-y-3 rounded border border-slate-800 p-2">
                  <Field label="body_html (optional)">
                    <TextArea
                      value={compose.form.bodyHtml}
                      onChange={(bodyHtml) => compose.update({ bodyHtml })}
                      rows={3}
                      placeholder="<p>…</p>"
                    />
                  </Field>
                  {compose.form.push && (
                    <>
                      <Field label="push priority (1–5)">
                        <TextInput
                          value={compose.form.pushPriority}
                          onChange={(pushPriority) => compose.update({ pushPriority })}
                        />
                      </Field>
                      <Field label="push tags (comma-separated)">
                        <TextInput
                          value={compose.form.pushTags}
                          onChange={(pushTags) => compose.update({ pushTags })}
                          placeholder="warning,backup"
                        />
                      </Field>
                      <Field label="push click URL">
                        <TextInput
                          value={compose.form.pushClick}
                          onChange={(pushClick) => compose.update({ pushClick })}
                          placeholder="https://…"
                        />
                      </Field>
                    </>
                  )}
                </div>
              )}
              <SubmitNote state={compose.submitState} />
              <button
                type="submit"
                disabled={compose.submitState.status === "sending"}
                className="w-full rounded bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
              >
                {compose.submitState.status === "sending" ? "sending…" : "Send"}
              </button>
            </form>
          </Panel>
        </div>

        <div className="col-span-12 lg:col-span-5">
          <Panel title={`History (${visible.length})`}>
            <div className="mb-2 flex flex-wrap gap-1">
              {CHANNEL_FILTERS.map((filter) => (
                <button
                  key={filter}
                  type="button"
                  onClick={() => setChannelFilter(filter)}
                  className={`rounded px-1.5 py-0.5 text-[11px] ${
                    channelFilter === filter
                      ? "bg-slate-700 text-slate-100"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {filter}
                </button>
              ))}
              <span className="mx-1 text-slate-700">|</span>
              {STATUS_FILTERS.map((filter) => (
                <button
                  key={filter}
                  type="button"
                  onClick={() => setStatusFilter(filter)}
                  className={`rounded px-1.5 py-0.5 text-[11px] ${
                    statusFilter === filter
                      ? "bg-slate-700 text-slate-100"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {filter.replace("_", " ")}
                </button>
              ))}
            </div>
            <ul className="space-y-1.5">
              {visible.map((notification) => {
                const expanded = selectedId === notification.id;
                return (
                  <li key={notification.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(expanded ? null : notification.id)}
                      className="w-full rounded border border-slate-800 bg-slate-900/60 px-2.5 py-2 text-left hover:border-slate-700"
                    >
                      <div className="flex items-center gap-2">
                        <StatusDot status={notificationStatus(notification)} />
                        <span className="truncate text-sm">{notification.subject}</span>
                        <span className="ml-auto shrink-0 text-[11px] tabular-nums text-slate-500">
                          {clockTime(notification.created_at)}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-1.5 pl-4">
                        <span className="text-[11px] text-slate-500">{notification.source}</span>
                        {notification.deliveries.map((delivery) => (
                          <ChannelTag key={delivery.id} channel={delivery.channel} />
                        ))}
                        <StatusChip status={notificationStatus(notification)} />
                        <span className="ml-auto text-[11px] text-slate-600">
                          {timeAgo(notification.created_at)}
                        </span>
                      </div>
                    </button>
                    {expanded && (
                      <div className="mt-1.5 space-y-1.5 pl-4">
                        {notification.deliveries.map((delivery) => (
                          <DeliveryDetail
                            key={delivery.id}
                            delivery={delivery}
                            onRetry={(id) => void store.retry(id)}
                          />
                        ))}
                      </div>
                    )}
                  </li>
                );
              })}
              {visible.length === 0 && (
                <li className="py-6 text-center text-xs text-slate-600">nothing matches</li>
              )}
            </ul>
          </Panel>
        </div>

        <div className="col-span-12 space-y-3 lg:col-span-4">
          <Panel title="Health">
            <ul className="space-y-1.5 text-sm">
              {store.health.map((check) => (
                <li key={check.service_name} className="flex items-center gap-2">
                  <StatusDot status={check.is_healthy ? "succeeded" : "failed"} />
                  <span>{check.service_name}</span>
                  <span
                    className={`ml-auto text-[11px] ${check.is_healthy ? "text-emerald-400" : "text-rose-400"}`}
                  >
                    {check.is_healthy ? "healthy" : "unhealthy"}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] text-slate-600">
              last checked {clockTime(store.health[0]?.timestamp ?? new Date().toISOString())}
            </p>
          </Panel>
          <Panel title="Channels">
            <ul className="space-y-2 text-sm">
              {channelConfig.map((entry) => (
                <li key={entry.channel}>
                  <div className="flex items-center gap-2">
                    <ChannelTag channel={entry.channel} />
                    <span className="text-xs text-slate-300">{entry.provider}</span>
                    <span className="ml-auto text-[11px] text-emerald-400">configured</span>
                  </div>
                  <p className="mt-0.5 text-[11px] text-slate-500">{entry.endpoint}</p>
                  <p className="text-[11px] text-slate-600">{entry.detail}</p>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </main>
    </div>
  );
}
