import type {
  Channel,
  ChannelConfigRequestDTO,
  ChannelConfigResponse,
  DeliveryResponse,
  ErrorEnvelope,
  HealthCheckResult,
  NotificationDetailResponse,
  NotificationPageResponse,
  NotificationRequestDTO,
} from "./types.ts";

const BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly envelope: ErrorEnvelope | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let envelope: ErrorEnvelope | null = null;
    try {
      envelope = (await res.json()) as ErrorEnvelope;
    } catch {
      /* non-JSON body */
    }
    throw new ApiError(res.status, envelope?.detail ?? res.statusText, envelope);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function json(body: unknown): RequestInit {
  return { body: JSON.stringify(body) };
}

export const api = {
  getHealth(): Promise<HealthCheckResult[]> {
    return request("/health");
  },

  listNotifications(query: string): Promise<NotificationPageResponse> {
    return request(`/notifications${query === "" ? "" : `?${query}`}`);
  },

  getNotification(id: number): Promise<NotificationDetailResponse> {
    return request(`/notifications/${id}`);
  },

  createNotification(body: NotificationRequestDTO): Promise<NotificationDetailResponse> {
    return request("/notifications", { method: "POST", ...json(body) });
  },

  retryDelivery(id: number): Promise<DeliveryResponse> {
    return request(`/deliveries/${id}/retry`, { method: "POST" });
  },

  getChannels(): Promise<ChannelConfigResponse[]> {
    return request("/channels");
  },

  putChannel(channel: Channel, body: ChannelConfigRequestDTO): Promise<ChannelConfigResponse> {
    return request(`/channels/${channel}`, { method: "PUT", ...json(body) });
  },

  deleteChannel(channel: Channel): Promise<void> {
    return request(`/channels/${channel}`, { method: "DELETE" });
  },
};
