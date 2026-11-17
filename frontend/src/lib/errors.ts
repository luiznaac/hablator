import type { ErrorEnvelope } from "../api/types.ts";

// The API answers every failure with the scaffold envelope `{code, detail, errors?}`; the client
// attaches it to `ApiError`. This turns any thrown value into one line the console can render
// above the action that failed.

function envelopeOf(error: unknown): ErrorEnvelope | null {
  if (error === null || typeof error !== "object" || !("envelope" in error)) return null;
  const envelope = (error as { envelope?: unknown }).envelope;
  if (envelope === null || typeof envelope !== "object") return null;
  if (!("detail" in envelope)) return null;
  return envelope as ErrorEnvelope;
}

export function formatApiError(error: unknown): string {
  const envelope = envelopeOf(error);
  if (envelope !== null) {
    const errors = envelope.errors ?? [];
    if (errors.length === 0) return envelope.detail;
    const fields = errors.map((item) => `${item.field}: ${item.message}`).join("; ");
    return `${envelope.detail} (${fields})`;
  }
  if (error instanceof Error) return error.message;
  return String(error);
}
