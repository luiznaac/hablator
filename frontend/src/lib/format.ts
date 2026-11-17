import type { Channel, DeliveryStatus, NotificationStatus } from "../api/types.ts";

// Pure formatting helpers — no React imports here (see AGENTS.md). This is what gets unit-tested
// in src/lib/**, since these repos don't have component-render tests yet.

export function formatHealthStatus(isHealthy: boolean): string {
  return isHealthy ? "healthy" : "unhealthy";
}

export function formatStatus(status: DeliveryStatus | NotificationStatus): string {
  return status.replace("_", " ");
}

const pad = (value: number) => String(value).padStart(2, "0");

export function formatTimestamp(iso: string | null): string {
  if (iso === null) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function formatTimeAgo(iso: string, now: Date = new Date()): string {
  const seconds = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

// A key the API would reject as secret-shaped (see backend/docs/api.md → Channels). The API never
// returns one, but a summary must never render a value even if the contract drifts.
const SECRET_KEY = /(api_key|token|secret|password|auth)/i;

function isSecretKey(key: string): boolean {
  return SECRET_KEY.test(key);
}
const CONFIG_LABELS: Record<string, string> = {
  from: "from",
  bcc: "bcc",
  topic: "topic",
  default_priority: "default priority",
};

function formatConfigValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (value !== null && typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** Presence-only summary of a channel's non-secret provider config. */
export function summarizeChannelConfig(
  channel: Channel,
  config: Record<string, unknown> | null,
): string {
  if (config === null) return "not configured";

  const parts: string[] = [];
  for (const [key, value] of Object.entries(config)) {
    if (isSecretKey(key)) {
      parts.push(`${key} set in the environment`);
      continue;
    }
    if (key === "recipients" && Array.isArray(value)) {
      parts.push(`${value.length} default recipients`);
      continue;
    }
    parts.push(`${CONFIG_LABELS[key] ?? key} ${formatConfigValue(value)}`);
  }
  return parts.length > 0 ? parts.join(" · ") : `${channel} configured`;
}
