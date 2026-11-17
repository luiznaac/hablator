import { describe, expect, it } from "vitest";
import { buildNotificationRequest, emptyComposeForm, validateCompose } from "./compose.ts";

describe("buildNotificationRequest", () => {
  it("builds an email-only request and omits an empty source and body_html", () => {
    const request = buildNotificationRequest({
      ...emptyComposeForm,
      subject: "  Backup finished ",
      body: "plain text",
      email: true,
      emailRecipient: " ops@example.com ",
    });

    expect(request).toEqual({
      source: null,
      content: { subject: "Backup finished", body: "plain text", body_html: null },
      channels: [{ channel: "email", recipients: ["ops@example.com"], options: {} }],
    });
  });

  it("builds a push-only request with normalized options and no recipients", () => {
    const request = buildNotificationRequest({
      ...emptyComposeForm,
      source: " valoab ",
      subject: "Backup",
      body: "done",
      email: false,
      push: true,
      pushPriority: "4",
      pushTags: " warning, backup ,, ",
      pushClick: " https://example.com/run/1 ",
    });

    expect(request.source).toBe("valoab");
    expect(request.channels).toEqual([
      {
        channel: "push",
        options: {
          priority: 4,
          tags: ["warning", "backup"],
          click: "https://example.com/run/1",
        },
      },
    ]);
  });

  it("keeps a priority alias as given and drops an empty advanced section", () => {
    const request = buildNotificationRequest({
      ...emptyComposeForm,
      subject: "s",
      body: "b",
      email: true,
      emailRecipient: "",
      push: true,
      pushPriority: "urgent",
      advanced: false,
    });

    expect(request.content.body_html).toBeNull();
    expect(request.channels).toEqual([
      { channel: "email", options: {} },
      { channel: "push", options: { priority: "urgent" } },
    ]);
  });

  it("sends body_html only when advanced content is present", () => {
    const request = buildNotificationRequest({
      ...emptyComposeForm,
      subject: "s",
      body: "b",
      bodyHtml: " <p>rich</p> ",
      email: true,
      emailRecipient: "ops@example.com",
      advanced: true,
    });

    expect(request.content.body_html).toBe("<p>rich</p>");
  });

  it("sends an empty channel list when nothing is toggled", () => {
    const request = buildNotificationRequest({
      ...emptyComposeForm,
      subject: "s",
      body: "b",
      email: false,
    });

    expect(request.channels).toEqual([]);
  });
});

describe("validateCompose", () => {
  it("requires at least one channel", () => {
    expect(validateCompose({ ...emptyComposeForm, subject: "s", body: "b", email: false })).toBe(
      "Pick at least one channel.",
    );
  });

  it("requires a subject and a body", () => {
    expect(validateCompose({ ...emptyComposeForm, body: "b" })).toBe("A subject is required.");
    expect(validateCompose({ ...emptyComposeForm, subject: "s", body: " " })).toBe(
      "A body is required.",
    );
  });

  it("passes a filled form", () => {
    expect(validateCompose({ ...emptyComposeForm, subject: "s", body: "b" })).toBeNull();
  });
});
