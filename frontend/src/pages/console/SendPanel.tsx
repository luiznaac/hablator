import { type FormEvent, useState } from "react";
import { useSendNotification } from "../../api/queries.ts";
import type { NotificationDetailResponse } from "../../api/types.ts";
import { Panel } from "../../components/Panel.tsx";
import {
  ChannelToggle,
  Field,
  Notice,
  TextArea,
  TextInput,
} from "../../components/console/fields.tsx";
import {
  type ComposeForm,
  buildNotificationRequest,
  emptyComposeForm,
  validateCompose,
} from "../../lib/compose.ts";
import { formatApiError } from "../../lib/errors.ts";

type Success = Pick<NotificationDetailResponse, "id" | "status">;

export function SendPanel() {
  const [form, setForm] = useState<ComposeForm>(emptyComposeForm);
  const [success, setSuccess] = useState<Success | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const send = useSendNotification();

  const update = (patch: Partial<ComposeForm>) => {
    setForm((previous) => ({ ...previous, ...patch }));
    setSuccess(null);
    setProblem(null);
    send.reset();
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSuccess(null);
    const gap = validateCompose(form);
    if (gap !== null) {
      setProblem(gap);
      return;
    }
    setProblem(null);
    send.mutate(buildNotificationRequest(form), {
      onSuccess: (notification) => {
        setSuccess({ id: notification.id, status: notification.status });
        setForm((previous) => ({ ...previous, subject: "", body: "", bodyHtml: "" }));
      },
    });
  };

  return (
    <Panel title="Send">
      <form className="space-y-3" onSubmit={submit}>
        <Field label="source">
          <TextInput
            value={form.source}
            onChange={(source) => update({ source })}
            placeholder="manual"
          />
        </Field>
        <Field label="subject">
          <TextInput
            value={form.subject}
            onChange={(subject) => update({ subject })}
            placeholder="What happened?"
          />
        </Field>
        <Field label="body">
          <TextArea
            value={form.body}
            onChange={(body) => update({ body })}
            rows={4}
            placeholder="Plain-text body"
          />
        </Field>

        <div className="flex gap-1.5">
          <ChannelToggle
            checked={form.email}
            onChange={(email) => update({ email })}
            label="email"
          />
          <ChannelToggle checked={form.push} onChange={(push) => update({ push })} label="push" />
        </div>

        {form.email && (
          <Field label="email recipient">
            <TextInput
              value={form.emailRecipient}
              onChange={(emailRecipient) => update({ emailRecipient })}
              placeholder="ops@example.com (blank uses the channel default)"
            />
          </Field>
        )}
        {form.push && (
          <p className="text-[11px] text-slate-500">
            push goes to the topic in the channel config — no recipient here
          </p>
        )}

        <button
          type="button"
          onClick={() => update({ advanced: !form.advanced })}
          className="text-[11px] text-slate-500 hover:text-slate-300"
        >
          {form.advanced ? "− hide advanced" : "+ advanced"}
        </button>

        {form.advanced && (
          <div className="space-y-3 rounded border border-slate-800 p-2">
            <Field label="body_html (optional)">
              <TextArea
                value={form.bodyHtml}
                onChange={(bodyHtml) => update({ bodyHtml })}
                rows={3}
                placeholder="<p>…</p>"
              />
            </Field>
            {form.push && (
              <>
                <Field label="push priority (1–5 or min/low/default/high/urgent)">
                  <TextInput
                    value={form.pushPriority}
                    onChange={(pushPriority) => update({ pushPriority })}
                    placeholder="default"
                  />
                </Field>
                <Field label="push tags (comma-separated)">
                  <TextInput
                    value={form.pushTags}
                    onChange={(pushTags) => update({ pushTags })}
                    placeholder="warning,backup"
                  />
                </Field>
                <Field label="push click URL">
                  <TextInput
                    value={form.pushClick}
                    onChange={(pushClick) => update({ pushClick })}
                    placeholder="https://…"
                  />
                </Field>
              </>
            )}
          </div>
        )}

        {problem !== null && <Notice tone="error">{problem}</Notice>}
        {send.error !== null && <Notice tone="error">{formatApiError(send.error)}</Notice>}
        {success !== null && (
          <Notice tone="success">
            notification #{success.id} · {success.status}
          </Notice>
        )}

        <button
          type="submit"
          disabled={send.isPending}
          className="w-full rounded bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
        >
          {send.isPending ? "sending…" : "Send"}
        </button>
      </form>
    </Panel>
  );
}
