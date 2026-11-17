import type { Channel, DeliveryResponse, NotificationStatus } from "../api/types.ts";

// History filters and offset pager math, kept pure so the query string, page numbers and the
// retry gate are unit-tested instead of buried in the panel.

export interface HistoryFilters {
  channel: Channel | "all";
  status: NotificationStatus | "all";
}

export const HISTORY_PAGE_SIZE = 20;

export const defaultHistoryFilters: HistoryFilters = {
  channel: "all",
  status: "all",
};

export function buildHistoryQuery(filters: HistoryFilters, offset: number): string {
  const params = new URLSearchParams();
  params.set("limit", String(HISTORY_PAGE_SIZE));
  params.set("offset", String(offset));
  if (filters.channel !== "all") params.set("channel", filters.channel);
  if (filters.status !== "all") params.set("status", filters.status);
  return params.toString();
}

export function pageCount(total: number, limit: number = HISTORY_PAGE_SIZE): number {
  return Math.max(1, Math.ceil(total / limit));
}

/**
 * A failed delivery is retryable from the console only when its latest attempt says the failure
 * is transient. A permanent failure (e.g. a 401) would fail identically, and the spec asks for a
 * Retry action on retriable failures only.
 */
export function canRetry(delivery: DeliveryResponse): boolean {
  if (delivery.status !== "failed") return false;
  const latest = delivery.attempts[delivery.attempts.length - 1];
  return latest !== undefined && latest.outcome === "failed" && latest.retriable;
}
