import { describe, expect, it } from "vitest";
import type { AttemptResponse, DeliveryResponse } from "../api/types.ts";
import { buildHistoryQuery, canRetry, defaultHistoryFilters, pageCount } from "./history.ts";

describe("buildHistoryQuery", () => {
  it("sends only the paging when every filter is 'all'", () => {
    expect(buildHistoryQuery(defaultHistoryFilters, 0)).toBe("limit=20&offset=0");
  });

  it("includes the selected channel and status", () => {
    const query = buildHistoryQuery({ channel: "push", status: "failed" }, 40);

    expect(query).toBe("limit=20&offset=40&channel=push&status=failed");
  });
});

describe("pageCount", () => {
  it("is at least one page for an empty history", () => {
    expect(pageCount(0, 20)).toBe(1);
  });

  it("rounds a partial last page up", () => {
    expect(pageCount(41, 20)).toBe(3);
  });
});

function attempt(overrides: Partial<AttemptResponse>): AttemptResponse {
  return {
    attempt_number: 1,
    outcome: "failed",
    provider: "mailgun",
    provider_status: 503,
    error_kind: "http_status",
    error_message: "unavailable",
    retriable: true,
    started_at: "2026-11-17T12:00:00Z",
    finished_at: "2026-11-17T12:00:01Z",
    ...overrides,
  };
}

function delivery(overrides: Partial<DeliveryResponse>): DeliveryResponse {
  return {
    id: 1,
    channel: "email",
    status: "failed",
    recipients: ["ops@example.com"],
    content: { subject: "s", body: "b", body_html: null },
    options: {},
    next_attempt_at: null,
    created_at: "2026-11-17T12:00:00Z",
    updated_at: "2026-11-17T12:00:00Z",
    attempts: [attempt({})],
    ...overrides,
  };
}

describe("canRetry", () => {
  it("allows a failed delivery whose latest attempt is retriable", () => {
    expect(canRetry(delivery({}))).toBe(true);
  });

  it("refuses a permanent failure", () => {
    expect(
      canRetry(delivery({ attempts: [attempt({ retriable: false, provider_status: 401 })] })),
    ).toBe(false);
  });

  it("refuses a pending delivery", () => {
    expect(canRetry(delivery({ status: "pending", attempts: [] }))).toBe(false);
  });

  it("refuses a delivery with no attempts", () => {
    expect(canRetry(delivery({ attempts: [] }))).toBe(false);
  });
});
