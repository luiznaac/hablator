// PROTOTYPE — the send-form state shared by the three variants (issue #19). Each variant renders
// its own layout; only this state machine is shared, so the variants stay structurally different.

import { useState } from "react";
import type { PrototypeStore, SendInput } from "./store.ts";

export interface ComposeForm {
  source: string;
  subject: string;
  body: string;
  bodyHtml: string;
  email: boolean;
  emailRecipient: string;
  push: boolean;
  pushRecipient: string;
  pushPriority: string;
  pushTags: string;
  pushClick: string;
  advanced: boolean;
}

export type SubmitState =
  | { status: "idle" }
  | { status: "sending" }
  | { status: "sent"; message: string }
  | { status: "error"; message: string };

const initialForm: ComposeForm = {
  source: "manual",
  subject: "",
  body: "",
  bodyHtml: "",
  email: true,
  emailRecipient: "rafa@example.com",
  push: false,
  pushRecipient: "hablator",
  pushPriority: "3",
  pushTags: "",
  pushClick: "",
  advanced: false,
};

export function useCompose(store: PrototypeStore) {
  const [form, setForm] = useState<ComposeForm>(initialForm);
  const [submitState, setSubmitState] = useState<SubmitState>({ status: "idle" });

  const update = (patch: Partial<ComposeForm>) => {
    setForm((previous) => ({ ...previous, ...patch }));
    setSubmitState((previous) => (previous.status === "error" ? { status: "idle" } : previous));
  };

  const submit = async () => {
    setSubmitState({ status: "sending" });
    const channels: SendInput["channels"] = [];
    if (form.email) {
      channels.push({ channel: "email", recipient: form.emailRecipient, options: {} });
    }
    if (form.push) {
      const options: Record<string, string> = { priority: form.pushPriority };
      if (form.pushTags.trim()) options.tags = form.pushTags.trim();
      if (form.pushClick.trim()) options.click = form.pushClick.trim();
      channels.push({ channel: "push", recipient: form.pushRecipient, options });
    }

    const outcome = await store.send({
      source: form.source,
      subject: form.subject,
      body: form.body,
      bodyHtml: form.bodyHtml.trim() ? form.bodyHtml : null,
      channels,
    });

    if (outcome.ok) {
      setSubmitState({ status: "sent", message: `notification #${outcome.id} queued` });
      setForm((previous) => ({ ...previous, subject: "", body: "", bodyHtml: "" }));
    } else {
      setSubmitState({ status: "error", message: outcome.message });
    }
  };

  return { form, update, submit, submitState };
}
