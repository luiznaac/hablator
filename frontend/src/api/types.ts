// Hand-maintained mirror of the backend's edge DTOs — see AGENTS.md and salgadinhos'
// `api-contract` skill. Any DTO change on the backend must update this file in the same commit.

export interface HealthCheckResult {
  service_name: string;
  is_healthy: boolean;
  timestamp: string;
}

export type Channel = "email" | "push" | "sms" | "voice";

export interface ContentDTO {
  subject: string;
  body: string;
  body_html?: string | null;
}

export interface ChannelContentDTO {
  subject?: string | null;
  body?: string | null;
  body_html?: string | null;
}

export interface ChannelRequestDTO {
  channel: Channel;
  recipients?: string[] | null;
  content?: ChannelContentDTO | null;
  options?: Record<string, unknown>;
}

export interface NotificationRequestDTO {
  source?: string | null;
  content: ContentDTO;
  channels: ChannelRequestDTO[];
}

export interface ContentResponse {
  subject: string | null;
  body: string;
  body_html: string | null;
}

export type AttemptOutcome = "succeeded" | "failed";

export interface AttemptResponse {
  attempt_number: number;
  outcome: AttemptOutcome;
  provider: string;
  provider_status: number | null;
  error_kind: string | null;
  error_message: string | null;
  retriable: boolean;
  started_at: string;
  finished_at: string | null;
}

export type DeliveryStatus = "pending" | "in_progress" | "succeeded" | "failed";

export interface DeliveryResponse {
  id: number;
  channel: Channel;
  status: DeliveryStatus;
  recipients: string[];
  content: ContentResponse;
  options: Record<string, unknown>;
  next_attempt_at: string | null;
  created_at: string;
  updated_at: string;
  attempts: AttemptResponse[];
}

export type NotificationStatus = "pending" | "succeeded" | "failed";

export interface NotificationDetailResponse {
  id: number;
  source: string | null;
  content: ContentResponse;
  status: NotificationStatus;
  created_at: string;
  deliveries: DeliveryResponse[];
}

export interface ErrorItem {
  field: string;
  message: string;
}

export interface ErrorEnvelope {
  code: string;
  detail: string;
  errors?: ErrorItem[] | null;
}
