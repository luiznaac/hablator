import { type FormEvent, useState } from "react";
import { useChannels, useDisableChannel, useSaveChannel } from "../../api/queries.ts";
import type { Channel, ChannelConfigResponse } from "../../api/types.ts";
import { Panel } from "../../components/Panel.tsx";
import { ChannelTag } from "../../components/console/atoms.tsx";
import { Field, Notice, TextInput } from "../../components/console/fields.tsx";
import { formatApiError } from "../../lib/errors.ts";
import { formatTimestamp, summarizeChannelConfig } from "../../lib/format.ts";
import { parsePriority, splitCommaList } from "../../lib/values.ts";

interface Draft {
  from: string;
  bcc: string;
  recipients: string;
  topic: string;
  defaultPriority: string;
}

const emptyDraft: Draft = {
  from: "",
  bcc: "",
  recipients: "",
  topic: "",
  defaultPriority: "",
};

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function draftFrom(entry: ChannelConfigResponse): Draft {
  const config = entry.config ?? {};
  return {
    from: stringValue(config.from),
    bcc: stringValue(config.bcc),
    recipients: Array.isArray(config.recipients) ? config.recipients.map(String).join(", ") : "",
    topic: stringValue(config.topic),
    defaultPriority: config.default_priority === undefined ? "" : String(config.default_priority),
  };
}

function providerFor(channel: Channel): string | null {
  if (channel === "email") return "mailgun";
  if (channel === "push") return "ntfy";
  return null;
}

function configFor(channel: Channel, draft: Draft): Record<string, unknown> {
  if (channel === "email") {
    const config: Record<string, unknown> = { from: draft.from.trim() };
    if (draft.bcc.trim() !== "") config.bcc = draft.bcc.trim();
    const recipients = splitCommaList(draft.recipients);
    if (recipients.length > 0) config.recipients = recipients;
    return config;
  }
  const config: Record<string, unknown> = { topic: draft.topic.trim() };
  const priority = parsePriority(draft.defaultPriority);
  if (priority !== undefined) {
    config.default_priority = priority;
  }
  return config;
}

export function ChannelsPanel() {
  const channels = useChannels();
  const save = useSaveChannel();
  const disable = useDisableChannel();
  const [editing, setEditing] = useState<Channel | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft);

  const startEdit = (entry: ChannelConfigResponse) => {
    save.reset();
    setDraft(draftFrom(entry));
    setEditing(entry.channel);
  };

  const update = (patch: Partial<Draft>) => setDraft((previous) => ({ ...previous, ...patch }));

  const submit = (event: FormEvent<HTMLFormElement>, channel: Channel) => {
    event.preventDefault();
    const provider = providerFor(channel);
    if (provider === null) return;
    save.mutate(
      { channel, body: { provider, config: configFor(channel, draft) } },
      { onSuccess: () => setEditing(null) },
    );
  };

  return (
    <Panel title="Channels">
      {channels.isLoading && <p className="text-xs text-slate-600">loading…</p>}
      {channels.error !== null && <Notice tone="error">{formatApiError(channels.error)}</Notice>}
      {disable.error !== null && <Notice tone="error">{formatApiError(disable.error)}</Notice>}

      <ul className="space-y-2 text-sm">
        {channels.data?.map((entry) => {
          const editable = providerFor(entry.channel) !== null;
          const disabling = disable.isPending && disable.variables === entry.channel;
          return (
            <li key={entry.channel} className="rounded border border-slate-800 px-2.5 py-2">
              <div className="flex items-center gap-2">
                <ChannelTag channel={entry.channel} />
                <span className="text-xs text-slate-300">{entry.provider ?? "no provider"}</span>
                <span
                  className={`ml-auto text-[11px] ${entry.configured ? "text-emerald-400" : "text-slate-500"}`}
                >
                  {entry.configured ? "configured" : "unconfigured"}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                {summarizeChannelConfig(entry.channel, entry.config)}
              </p>
              {editable && (
                <p className="text-[11px] text-slate-600">secrets set in the environment</p>
              )}
              {!editable && (
                <p className="text-[11px] text-slate-600">
                  vocabulary only — no provider registered
                </p>
              )}
              {entry.updated_at !== null && (
                <p className="text-[11px] text-slate-600">
                  updated {formatTimestamp(entry.updated_at)}
                </p>
              )}

              {editable && editing !== entry.channel && (
                <div className="mt-1.5 flex gap-1.5">
                  <button
                    type="button"
                    onClick={() => startEdit(entry)}
                    className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px] text-slate-200 hover:bg-slate-700"
                  >
                    Edit
                  </button>
                  {entry.configured && (
                    <button
                      type="button"
                      disabled={disabling}
                      onClick={() => disable.mutate(entry.channel)}
                      className="rounded px-1.5 py-0.5 text-[11px] text-rose-300 hover:text-rose-200 disabled:opacity-50"
                    >
                      {disabling ? "disabling…" : "Disable"}
                    </button>
                  )}
                </div>
              )}

              {editing === entry.channel && (
                <form className="mt-2 space-y-2" onSubmit={(event) => submit(event, entry.channel)}>
                  {entry.channel === "email" ? (
                    <>
                      <Field label="from (required)">
                        <TextInput value={draft.from} onChange={(from) => update({ from })} />
                      </Field>
                      <Field label="bcc (optional)">
                        <TextInput value={draft.bcc} onChange={(bcc) => update({ bcc })} />
                      </Field>
                      <Field label="default recipients (optional, comma-separated)">
                        <TextInput
                          value={draft.recipients}
                          onChange={(recipients) => update({ recipients })}
                        />
                      </Field>
                    </>
                  ) : (
                    <>
                      <Field label="topic (required)">
                        <TextInput value={draft.topic} onChange={(topic) => update({ topic })} />
                      </Field>
                      <Field label="default priority (1–5, optional)">
                        <TextInput
                          value={draft.defaultPriority}
                          onChange={(defaultPriority) => update({ defaultPriority })}
                        />
                      </Field>
                    </>
                  )}

                  {save.error !== null && (
                    <Notice tone="error">{formatApiError(save.error)}</Notice>
                  )}

                  <div className="flex gap-1.5">
                    <button
                      type="submit"
                      disabled={save.isPending}
                      className="rounded bg-sky-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-sky-500 disabled:opacity-50"
                    >
                      {save.isPending ? "saving…" : "Save"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditing(null)}
                      className="rounded px-2 py-1 text-[11px] text-slate-400 hover:text-slate-200"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
