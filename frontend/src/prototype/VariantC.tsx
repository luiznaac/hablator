// PROTOTYPE — variant C: a dense history table with a right-hand inspector and an inline send
// bar (issue #19).

import { useState } from "react";
import { ChannelTag, StatusChip, StatusDot } from "./atoms.tsx";
import { useCompose } from "./compose.ts";
import { ChannelToggle, Field, SubmitNote, TextInput } from "./fields.tsx";
import { notificationStatus } from "./fixtures.ts";
import { clockTime, timeAgo } from "./format.ts";
import type { PrototypeStore } from "./store.ts";

export function VariantC({ store }: { store: PrototypeStore }) {
  const compose = useCompose(store);
  const [selectedId, setSelectedId] = useState<number | null>(store.notifications[0]?.id ?? null);
  const selected = store.notifications.find((notification) => notification.id === selectedId);

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-200">
      <header className="flex items-center gap-3 border-b border-slate-800 px-4 py-2">
        <h1 className="text-sm font-semibold">hablator</h1>
        <span className="text-[11px] text-slate-500">table + inspector</span>
        <div className="ml-auto flex items-center gap-3 text-[11px] text-slate-400">
          {store.health.map((check) => (
            <span key={check.service_name} className="flex items-center gap-1.5">
              <StatusDot status={check.is_healthy ? "succeeded" : "failed"} />
              {check.service_name}
            </span>
          ))}
        </div>
      </header>

      <form
        className="flex flex-wrap items-end gap-2 border-b border-slate-800 bg-slate-900/40 px-4 py-2.5"
        onSubmit={(event) => {
          event.preventDefault();
          void compose.submit();
        }}
      >
        <div className="flex gap-1 pb-1">
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
        <div className="w-48">
          <Field label="recipient">
            <TextInput
              value={compose.form.email ? compose.form.emailRecipient : compose.form.pushRecipient}
              onChange={(recipient) =>
                compose.update(
                  compose.form.email ? { emailRecipient: recipient } : { pushRecipient: recipient },
                )
              }
            />
          </Field>
        </div>
        <div className="min-w-40 flex-1">
          <Field label="subject">
            <TextInput
              value={compose.form.subject}
              onChange={(subject) => compose.update({ subject })}
              placeholder="What happened?"
            />
          </Field>
        </div>
        <div className="min-w-48 flex-[2]">
          <Field label="body">
            <TextInput
              value={compose.form.body}
              onChange={(body) => compose.update({ body })}
              placeholder="Plain-text body"
            />
          </Field>
        </div>
        <button
          type="submit"
          disabled={compose.submitState.status === "sending"}
          className="rounded bg-sky-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
        >
          {compose.submitState.status === "sending" ? "sending…" : "Send"}
        </button>
        <div className="w-full empty:hidden">
          <SubmitNote state={compose.submitState} />
        </div>
      </form>

      <div className="grid flex-1 grid-cols-12">
        <div className="col-span-8 overflow-auto">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-slate-900 text-[10px] uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2 font-medium">time</th>
                <th className="px-3 py-2 font-medium">source</th>
                <th className="px-3 py-2 font-medium">subject</th>
                <th className="px-3 py-2 font-medium">channels</th>
                <th className="px-3 py-2 font-medium">status</th>
              </tr>
            </thead>
            <tbody>
              {store.notifications.map((notification) => {
                const isSelected = notification.id === selectedId;
                return (
                  <tr
                    key={notification.id}
                    className={`border-b border-slate-900 ${isSelected ? "bg-slate-800/60" : "hover:bg-slate-900/60"}`}
                  >
                    <td className="whitespace-nowrap px-3 py-1.5 tabular-nums text-slate-500">
                      {timeAgo(notification.created_at)}
                    </td>
                    <td className="px-3 py-1.5 text-slate-400">{notification.source}</td>
                    <td className="px-3 py-1.5">
                      <button
                        type="button"
                        onClick={() => setSelectedId(notification.id)}
                        className="block max-w-[22rem] truncate text-left text-slate-200 hover:text-white"
                      >
                        {notification.subject}
                      </button>
                    </td>
                    <td className="px-3 py-1.5">
                      <div className="flex gap-1">
                        {notification.deliveries.map((delivery) => (
                          <ChannelTag key={delivery.id} channel={delivery.channel} />
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-1.5">
                      <StatusChip status={notificationStatus(notification)} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <aside className="col-span-4 overflow-auto border-l border-slate-800 p-3">
          {selected ? (
            <div className="space-y-3">
              <div>
                <div className="flex items-center gap-2">
                  <StatusChip status={notificationStatus(selected)} />
                  <span className="text-[11px] text-slate-500">#{selected.id}</span>
                </div>
                <h2 className="mt-1 text-sm font-medium">{selected.subject}</h2>
                <p className="text-[11px] text-slate-500">
                  {selected.source} · {clockTime(selected.created_at)} ·{" "}
                  {timeAgo(selected.created_at)}
                </p>
              </div>

              <div className="space-y-1.5">
                {selected.deliveries.map((delivery) => {
                  const retriableFailure = delivery.attempts.some(
                    (attempt) => attempt.status === "failed" && attempt.retriable,
                  );
                  return (
                    <div
                      key={delivery.id}
                      className="rounded border border-slate-800 bg-slate-900/60 p-2"
                    >
                      <div className="flex items-center gap-2 text-[11px]">
                        <ChannelTag channel={delivery.channel} />
                        <span className="truncate text-slate-400">{delivery.recipient}</span>
                        <span className="ml-auto">
                          <StatusChip status={delivery.status} />
                        </span>
                      </div>
                      {Object.entries(delivery.options).length > 0 && (
                        <p className="mt-1 text-[11px] text-slate-500">
                          {Object.entries(delivery.options)
                            .map(([key, value]) => `${key}=${value}`)
                            .join(" · ")}
                        </p>
                      )}
                      {delivery.attempts.map((attempt) => (
                        <p key={attempt.id} className="mt-1 text-[11px] text-slate-500">
                          {clockTime(attempt.attempted_at)} · {attempt.status}
                          {attempt.error ? ` · ${attempt.error}` : ""}
                        </p>
                      ))}
                      {retriableFailure && (
                        <button
                          type="button"
                          onClick={() => void store.retry(delivery.id)}
                          className="mt-1 rounded bg-slate-800 px-2 py-0.5 text-[11px] hover:bg-slate-700"
                        >
                          Retry
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>

              <div>
                <h3 className="mb-1 text-[10px] uppercase tracking-wide text-slate-500">
                  stored notification
                </h3>
                <pre className="overflow-auto rounded border border-slate-800 bg-slate-900/60 p-2 text-[10px] leading-relaxed text-slate-400">
                  {JSON.stringify(selected, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <p className="py-10 text-center text-xs text-slate-600">select a row to inspect it</p>
          )}
        </aside>
      </div>

      <footer className="flex items-center gap-3 border-t border-slate-800 px-4 py-1.5 text-[11px] text-slate-500">
        <span className="uppercase tracking-wide">health</span>
        {store.health.map((check) => (
          <span key={check.service_name} className="flex items-center gap-1.5">
            <StatusDot status={check.is_healthy ? "succeeded" : "failed"} />
            {check.service_name} {check.is_healthy ? "ok" : "failing"}
          </span>
        ))}
        <span className="ml-auto">
          checked {clockTime(store.health[0]?.timestamp ?? new Date().toISOString())}
        </span>
      </footer>
    </div>
  );
}
