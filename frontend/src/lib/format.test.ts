import { describe, expect, it } from "vitest";
import {
  formatHealthStatus,
  formatStatus,
  formatTimeAgo,
  formatTimestamp,
  summarizeChannelConfig,
} from "./format.ts";

describe("formatHealthStatus", () => {
  it("formats a healthy result", () => {
    expect(formatHealthStatus(true)).toBe("healthy");
  });

  it("formats an unhealthy result", () => {
    expect(formatHealthStatus(false)).toBe("unhealthy");
  });
});

describe("formatStatus", () => {
  it("renders in_progress with a space", () => {
    expect(formatStatus("in_progress")).toBe("in progress");
  });

  it("leaves a single-word status alone", () => {
    expect(formatStatus("succeeded")).toBe("succeeded");
  });
});

describe("formatTimestamp", () => {
  it("renders a fixed-width local date and time", () => {
    const iso = "2026-11-16T22:41:03.123456Z";
    const date = new Date(iso);
    const pad = (value: number) => String(value).padStart(2, "0");
    const expected = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;

    expect(formatTimestamp(iso)).toBe(expected);
  });

  it("renders a dash for a missing timestamp", () => {
    expect(formatTimestamp(null)).toBe("—");
  });
});

describe("formatTimeAgo", () => {
  const now = new Date("2026-11-17T12:00:00Z");

  it("calls the last minute 'just now'", () => {
    expect(formatTimeAgo("2026-11-17T11:59:30Z", now)).toBe("just now");
  });

  it("counts minutes, hours and days", () => {
    expect(formatTimeAgo("2026-11-17T11:30:00Z", now)).toBe("30m ago");
    expect(formatTimeAgo("2026-11-17T09:00:00Z", now)).toBe("3h ago");
    expect(formatTimeAgo("2026-11-14T12:00:00Z", now)).toBe("3d ago");
  });

  it("never counts into the future", () => {
    expect(formatTimeAgo("2026-11-17T12:05:00Z", now)).toBe("just now");
  });
});

describe("summarizeChannelConfig", () => {
  it("summarizes the email non-secret config", () => {
    expect(
      summarizeChannelConfig("email", {
        from: "ops@example.com",
        bcc: "archive@example.com",
        recipients: ["a@example.com", "b@example.com"],
      }),
    ).toBe("from ops@example.com · bcc archive@example.com · 2 default recipients");
  });

  it("summarizes the push non-secret config", () => {
    expect(summarizeChannelConfig("push", { topic: "hablator", default_priority: 3 })).toBe(
      "topic hablator · default priority 3",
    );
  });

  it("never renders a secret-shaped value", () => {
    const summary = summarizeChannelConfig("push", {
      topic: "hablator",
      api_token: "super-secret-value",
      ntfy_auth: "another-secret",
    });

    expect(summary).toContain("topic hablator");
    expect(summary).toContain("api_token set in the environment");
    expect(summary).toContain("ntfy_auth set in the environment");
    expect(summary).not.toContain("super-secret-value");
    expect(summary).not.toContain("another-secret");
  });

  it("says an unconfigured channel has no config", () => {
    expect(summarizeChannelConfig("email", null)).toBe("not configured");
  });
});
