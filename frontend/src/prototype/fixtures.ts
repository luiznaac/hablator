// PROTOTYPE — throwaway fixtures for the debug-UI shape prototype (issue #19).
//
// The shapes mirror the planned hub API (notification -> deliveries -> attempts) from the map's
// decisions, but nothing here talks to the backend: state is in memory and dies on reload.
// Nothing in this folder is meant to be folded into production as-is.

export type Channel = "email" | "push";
export type DeliveryStatus = "pending" | "in_progress" | "succeeded" | "failed";
export type NotificationStatus = "pending" | "in_progress" | "succeeded" | "failed" | "partial";

export interface Attempt {
  id: number;
  attempted_at: string;
  status: "succeeded" | "failed";
  retriable: boolean;
  error: string | null;
}

export interface Delivery {
  id: number;
  channel: Channel;
  recipient: string;
  status: DeliveryStatus;
  options: Record<string, string>;
  attempts: Attempt[];
}

export interface Notification {
  id: number;
  source: string;
  subject: string;
  body: string;
  body_html: string | null;
  created_at: string;
  deliveries: Delivery[];
}

export interface HealthCheck {
  service_name: string;
  is_healthy: boolean;
  timestamp: string;
}

export interface ChannelConfig {
  channel: Channel;
  provider: string;
  endpoint: string;
  detail: string;
}

export function notificationStatus(notification: Notification): NotificationStatus {
  const statuses = notification.deliveries.map((delivery) => delivery.status);
  if (statuses.some((status) => status === "in_progress")) return "in_progress";
  if (statuses.some((status) => status === "pending")) return "pending";
  if (statuses.every((status) => status === "succeeded")) return "succeeded";
  if (statuses.every((status) => status === "failed")) return "failed";
  return "partial";
}

const seededAt = Date.now();
const minutesAgo = (minutes: number) => new Date(seededAt - minutes * 60_000).toISOString();

export const seedHealth: HealthCheck[] = [
  { service_name: "app", is_healthy: true, timestamp: minutesAgo(0) },
  { service_name: "mysql", is_healthy: true, timestamp: minutesAgo(0) },
];

export const channelConfig: ChannelConfig[] = [
  {
    channel: "email",
    provider: "mailgun",
    endpoint: "api.mailgun.net/v3/hablator.invalid",
    detail: "from hablator@hablator.invalid · bcc archive on",
  },
  {
    channel: "push",
    provider: "ntfy",
    endpoint: "http://ntfy:8080",
    detail: "topic hablator · default priority 3 · 4 KB body cap",
  },
];

export const seedNotifications: Notification[] = [
  {
    id: 1042,
    source: "chameidor",
    subject: "Daily digest ready",
    body: "Your digest for Tuesday is ready.\n\nOpen the dashboard to read it.",
    body_html: "<p>Your digest for Tuesday is ready.</p>",
    created_at: minutesAgo(3),
    deliveries: [
      {
        id: 2041,
        channel: "email",
        recipient: "rafa@example.com",
        status: "succeeded",
        options: {},
        attempts: [
          {
            id: 3041,
            attempted_at: minutesAgo(3),
            status: "succeeded",
            retriable: false,
            error: null,
          },
        ],
      },
      {
        id: 2042,
        channel: "push",
        recipient: "hablator",
        status: "succeeded",
        options: { priority: "3", tags: "newspaper" },
        attempts: [
          {
            id: 3042,
            attempted_at: minutesAgo(3),
            status: "succeeded",
            retriable: false,
            error: null,
          },
        ],
      },
    ],
  },
  {
    id: 1041,
    source: "valoab",
    subject: "Backup finished",
    body: "Snapshot 2026-11-16 completed in 4m12s.",
    body_html: null,
    created_at: minutesAgo(22),
    deliveries: [
      {
        id: 2039,
        channel: "email",
        recipient: "rafa@example.com",
        status: "succeeded",
        options: {},
        attempts: [
          {
            id: 3039,
            attempted_at: minutesAgo(22),
            status: "succeeded",
            retriable: false,
            error: null,
          },
        ],
      },
    ],
  },
  {
    id: 1040,
    source: "curl",
    subject: "Test from terminal",
    body: "hello from curl",
    body_html: null,
    created_at: minutesAgo(65),
    deliveries: [
      {
        id: 2038,
        channel: "push",
        recipient: "hablator",
        status: "succeeded",
        options: { priority: "4" },
        attempts: [
          {
            id: 3038,
            attempted_at: minutesAgo(65),
            status: "succeeded",
            retriable: false,
            error: null,
          },
        ],
      },
    ],
  },
  {
    id: 1039,
    source: "chameidor",
    subject: "Scheduled job failed",
    body: "The nightly reconciliation job exited with status 1.",
    body_html: "<p>The nightly <strong>reconciliation</strong> job failed.</p>",
    created_at: minutesAgo(120),
    deliveries: [
      {
        id: 2036,
        channel: "email",
        recipient: "rafa@example.com",
        status: "failed",
        options: {},
        attempts: [
          {
            id: 3036,
            attempted_at: minutesAgo(120),
            status: "failed",
            retriable: false,
            error: "mailgun: 401 unauthorized (API_AUTH rejected)",
          },
        ],
      },
      {
        id: 2037,
        channel: "push",
        recipient: "hablator",
        status: "succeeded",
        options: { priority: "5", tags: "warning" },
        attempts: [
          {
            id: 3037,
            attempted_at: minutesAgo(120),
            status: "succeeded",
            retriable: false,
            error: null,
          },
        ],
      },
    ],
  },
  {
    id: 1038,
    source: "valoab",
    subject: "Weekly summary",
    body: "42 entries, 3 flagged for review.",
    body_html: null,
    created_at: minutesAgo(310),
    deliveries: [
      {
        id: 2035,
        channel: "email",
        recipient: "rafa@example.com",
        status: "failed",
        options: {},
        attempts: [
          {
            id: 3034,
            attempted_at: minutesAgo(310),
            status: "failed",
            retriable: true,
            error: "mailgun: timeout after 10s",
          },
        ],
      },
    ],
  },
  {
    id: 1037,
    source: "chameidor",
    subject: "Invoice due tomorrow",
    body: "Invoice 2026-11 is due tomorrow.",
    body_html: null,
    created_at: minutesAgo(1_560),
    deliveries: [
      {
        id: 2033,
        channel: "email",
        recipient: "rafa@example.com",
        status: "succeeded",
        options: {},
        attempts: [
          {
            id: 3032,
            attempted_at: minutesAgo(1_560),
            status: "succeeded",
            retriable: false,
            error: null,
          },
        ],
      },
      {
        id: 2034,
        channel: "push",
        recipient: "hablator",
        status: "succeeded",
        options: { priority: "3" },
        attempts: [
          {
            id: 3033,
            attempted_at: minutesAgo(1_560),
            status: "succeeded",
            retriable: false,
            error: null,
          },
        ],
      },
    ],
  },
  {
    id: 1036,
    source: "curl",
    subject: "hello",
    body: "ping",
    body_html: null,
    created_at: minutesAgo(1_740),
    deliveries: [
      {
        id: 2032,
        channel: "push",
        recipient: "hablator",
        status: "in_progress",
        options: { priority: "3" },
        attempts: [],
      },
    ],
  },
];
