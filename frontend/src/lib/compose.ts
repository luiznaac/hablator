import type { ChannelRequestDTO, NotificationRequestDTO } from "../api/types.ts";
import { parsePriority, splitCommaList } from "./values.ts";

// The send form's state and the pure mapping to the `POST /notifications` body. Everything the
// server validates stays server-validated — the console surfaces the returned envelope inline.

export interface ComposeForm {
  source: string;
  subject: string;
  body: string;
  bodyHtml: string;
  email: boolean;
  emailRecipient: string;
  push: boolean;
  pushPriority: string;
  pushTags: string;
  pushClick: string;
  advanced: boolean;
}

export const emptyComposeForm: ComposeForm = {
  source: "",
  subject: "",
  body: "",
  bodyHtml: "",
  email: true,
  emailRecipient: "",
  push: false,
  pushPriority: "",
  pushTags: "",
  pushClick: "",
  advanced: false,
};

/** The obvious client-side gaps; anything finer is the API's call and surfaces as an envelope. */
export function validateCompose(form: ComposeForm): string | null {
  if (!form.email && !form.push) return "Pick at least one channel.";
  if (form.subject.trim() === "") return "A subject is required.";
  if (form.body.trim() === "") return "A body is required.";
  return null;
}

function pushOptions(form: ComposeForm): Record<string, unknown> {
  const options: Record<string, unknown> = {};
  const priority = parsePriority(form.pushPriority);
  if (priority !== undefined) options.priority = priority;
  const tags = splitCommaList(form.pushTags);
  if (tags.length > 0) options.tags = tags;
  const click = form.pushClick.trim();
  if (click !== "") options.click = click;
  return options;
}

export function buildNotificationRequest(form: ComposeForm): NotificationRequestDTO {
  const channels: ChannelRequestDTO[] = [];

  if (form.email) {
    const recipient = form.emailRecipient.trim();
    channels.push({
      channel: "email",
      ...(recipient === "" ? {} : { recipients: [recipient] }),
      options: {},
    });
  }
  if (form.push) {
    channels.push({ channel: "push", options: pushOptions(form) });
  }

  const source = form.source.trim();
  const bodyHtml = form.bodyHtml.trim();

  return {
    source: source === "" ? null : source,
    content: {
      subject: form.subject.trim(),
      body: form.body,
      body_html: bodyHtml === "" ? null : bodyHtml,
    },
    channels,
  };
}
