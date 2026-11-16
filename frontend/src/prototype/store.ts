// PROTOTYPE — in-memory store for the debug-UI shape prototype (issue #19).
//
// Sends and retries are simulated: a recipient containing "fail" produces a failed attempt, so
// the error surfacing can be judged without a backend. Nothing persists; reload reseeds.

import { useRef, useState } from "react";
import {
  type Channel,
  type Delivery,
  type HealthCheck,
  type Notification,
  seedHealth,
  seedNotifications,
} from "./fixtures.ts";

export interface SendInput {
  source: string;
  subject: string;
  body: string;
  bodyHtml: string | null;
  channels: { channel: Channel; recipient: string; options: Record<string, string> }[];
}

export type SendResult = { ok: true; id: number } | { ok: false; message: string };

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export function usePrototypeStore() {
  const [notifications, setNotifications] = useState<Notification[]>(seedNotifications);
  const [health] = useState<HealthCheck[]>(seedHealth);
  const nextId = useRef(5000);

  async function send(input: SendInput): Promise<SendResult> {
    const source = input.source.trim();
    const subject = input.subject.trim();
    if (!source) return { ok: false, message: "source is required" };
    if (!subject) return { ok: false, message: "subject is required" };
    if (subject.length > 998) {
      return { ok: false, message: "subject is capped at 998 characters (422 validation_error)" };
    }
    if (input.channels.length === 0) {
      return { ok: false, message: "pick at least one channel (422 domain_error)" };
    }
    const missingRecipient = input.channels.some((entry) => !entry.recipient.trim());
    if (missingRecipient) return { ok: false, message: "every selected channel needs a recipient" };
    const oversizePush = input.channels.some(
      (entry) => entry.channel === "push" && new Blob([input.body]).size > 4 * 1024,
    );
    if (oversizePush) {
      return { ok: false, message: "push body is capped at 4 KB (422 domain_error)" };
    }

    await delay(700);

    const createdAt = new Date().toISOString();
    const deliveries: Delivery[] = input.channels.map((entry) => {
      const failed = entry.recipient.includes("fail");
      const error = failed
        ? entry.channel === "push"
          ? "ntfy: 403 forbidden (token lacks write on topic)"
          : "mailgun: 401 unauthorized (API_AUTH rejected)"
        : null;
      return {
        id: nextId.current++,
        channel: entry.channel,
        recipient: entry.recipient.trim(),
        status: failed ? "failed" : "succeeded",
        options: entry.options,
        attempts: [
          {
            id: nextId.current++,
            attempted_at: createdAt,
            status: failed ? "failed" : "succeeded",
            retriable: false,
            error,
          },
        ],
      };
    });

    const notification: Notification = {
      id: nextId.current++,
      source,
      subject,
      body: input.body,
      body_html: input.bodyHtml,
      created_at: createdAt,
      deliveries,
    };
    setNotifications((previous) => [notification, ...previous]);
    return { ok: true, id: notification.id };
  }

  async function retry(deliveryId: number): Promise<void> {
    const attemptedAt = new Date().toISOString();
    const attemptId = nextId.current++;
    setNotifications((previous) =>
      previous.map((notification) => ({
        ...notification,
        deliveries: notification.deliveries.map((delivery) =>
          delivery.id === deliveryId ? { ...delivery, status: "in_progress" } : delivery,
        ),
      })),
    );
    await delay(800);
    setNotifications((previous) =>
      previous.map((notification) => ({
        ...notification,
        deliveries: notification.deliveries.map((delivery) =>
          delivery.id === deliveryId
            ? {
                ...delivery,
                status: "succeeded",
                attempts: [
                  ...delivery.attempts,
                  {
                    id: attemptId,
                    attempted_at: attemptedAt,
                    status: "succeeded",
                    retriable: false,
                    error: null,
                  },
                ],
              }
            : delivery,
        ),
      })),
    );
  }

  return { notifications, health, send, retry };
}

export type PrototypeStore = ReturnType<typeof usePrototypeStore>;
