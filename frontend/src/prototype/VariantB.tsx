// PROTOTYPE — variant B: a full-width notification timeline with compose in a slide-over drawer,
// health as a header strip (issue #19).

import { useState } from "react";
import { ChannelTag, StatusChip, StatusDot } from "./atoms.tsx";
import { useCompose } from "./compose.ts";
import { ChannelToggle, Field, SubmitNote, TextArea, TextInput } from "./fields.tsx";
import { type Notification, notificationStatus } from "./fixtures.ts";
import { clockTime, groupByDay, timeAgo } from "./format.ts";
import type { PrototypeStore } from "./store.ts";

function TimelineDetail({
  notification,
  onRetry,
}: {
  notification: Notification;
  onRetry: (deliveryId: number) => void;
}) {
  return (
    <div className="mt-2 space-y-1.5 border-l border-slate-800 pl-3">
      {notification.deliveries.map((delivery) => {
        const retriableFailure = delivery.attempts.some(
          (attempt) => attempt.status === "failed" && attempt.retriable,
        );
        return (
          <div
            key={delivery.id}
            className="rounded border border-slate-800 bg-slate-900/60 px-2.5 py-1.5"
          >
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <ChannelTag channel={delivery.channel} />
              <span className="text-slate-400">{delivery.recipient}</span>
              {Object.entries(delivery.options).map(([key, value]) => (
                <span key={key} className="rounded bg-slate-800 px-1 text-slate-400">
                  {key}={value}
                </span>
              ))}
              <span className="ml-auto">
                <StatusChip status={delivery.status} />
              </span>
            </div>
            {delivery.attempts.map((attempt) => (
              <p key={attempt.id} className="mt-1 text-[11px] text-slate-500">
                attempt {clockTime(attempt.attempted_at)} · {attempt.status}
                {attempt.error ? ` · ${attempt.error}` : ""}
                {attempt.retriable ? " · retriable" : ""}
              </p>
            ))}
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
      })}
      {notification.body && (
        <p className="whitespace-pre-wrap text-[11px] text-slate-500">{notification.body}</p>
      )}
    </div>
  );
}

export function VariantB({ store }: { store: PrototypeStore }) {
  const compose = useCompose(store);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(store.notifications[0]?.id ?? null);
  const groups = groupByDay(store.notifications);
  const failing = store.health.filter((check) => !check.is_healthy);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-6 py-3">
          <h1 className="text-base font-semibold">hablator</h1>
          <span className="text-[11px] text-slate-500">notification timeline</span>
          <div className="ml-auto flex items-center gap-3 text-[11px]">
            {store.health.map((check) => (
              <span
                key={check.service_name}
                className={`flex items-center gap-1.5 ${
                  check.is_healthy ? "text-slate-400" : "text-rose-300"
                }`}
              >
                <StatusDot status={check.is_healthy ? "succeeded" : "failed"} />
                {check.service_name}
              </span>
            ))}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-6 pb-36">
        {failing.length > 0 && (
          <p className="mb-4 rounded bg-rose-500/10 px-3 py-2 text-xs text-rose-300 ring-1 ring-rose-500/30">
            {failing.length} health check{failing.length === 1 ? "" : "s"} failing
          </p>
        )}
        {groups.map(([day, items]) => (
          <section key={day} className="mb-8">
            <h2 className="mb-3 text-[11px] font-medium uppercase tracking-wide text-slate-500">
              {day}
            </h2>
            <ol className="relative space-y-3 border-l border-slate-800 pl-6">
              {items.map((notification) => {
                const expanded = expandedId === notification.id;
                return (
                  <li key={notification.id} className="relative">
                    <span className="absolute -left-[29px] top-3">
                      <StatusDot status={notificationStatus(notification)} />
                    </span>
                    <button
                      type="button"
                      onClick={() => setExpandedId(expanded ? null : notification.id)}
                      className="w-full rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2 text-left hover:border-slate-700"
                    >
                      <div className="flex items-baseline gap-2">
                        <span className="truncate text-sm font-medium">{notification.subject}</span>
                        <span className="ml-auto shrink-0 text-[11px] text-slate-500">
                          {timeAgo(notification.created_at)}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-500">
                        <span>{notification.source}</span>
                        {notification.deliveries.map((delivery) => (
                          <ChannelTag key={delivery.id} channel={delivery.channel} />
                        ))}
                        <StatusChip status={notificationStatus(notification)} />
                        <span className="ml-auto tabular-nums">
                          {clockTime(notification.created_at)}
                        </span>
                      </div>
                    </button>
                    {expanded && (
                      <TimelineDetail
                        notification={notification}
                        onRetry={(id) => void store.retry(id)}
                      />
                    )}
                  </li>
                );
              })}
            </ol>
          </section>
        ))}
      </main>

      <button
        type="button"
        onClick={() => setDrawerOpen(true)}
        className="fixed bottom-24 right-6 z-20 rounded-full bg-sky-600 px-5 py-2.5 text-sm font-medium text-white shadow-lg hover:bg-sky-500"
      >
        Send
      </button>

      {drawerOpen && (
        <div className="fixed inset-0 z-30">
          <button
            type="button"
            aria-label="Close send panel"
            onClick={() => setDrawerOpen(false)}
            className="absolute inset-0 bg-black/60"
          />
          <aside className="absolute inset-y-0 right-0 flex w-[420px] max-w-full flex-col border-l border-slate-800 bg-slate-950 p-4 shadow-2xl">
            <div className="mb-3 flex items-center">
              <h2 className="text-sm font-semibold">Send a notification</h2>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="ml-auto text-xs text-slate-500 hover:text-slate-300"
              >
                close
              </button>
            </div>
            <form
              className="space-y-3 overflow-y-auto pb-6"
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
          </aside>
        </div>
      )}
    </div>
  );
}
