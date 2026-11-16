// PROTOTYPE — shared atoms for the debug-UI shape prototype (issue #19). Only the small status
// vocabulary is shared; each variant owns its layout.

import type { Channel, DeliveryStatus, NotificationStatus } from "./fixtures.ts";

type AnyStatus = DeliveryStatus | NotificationStatus;

const STATUS_TONE: Record<AnyStatus, string> = {
  pending: "bg-slate-700/60 text-slate-300 ring-slate-600",
  in_progress: "bg-sky-500/15 text-sky-300 ring-sky-500/40",
  succeeded: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/40",
  failed: "bg-rose-500/15 text-rose-300 ring-rose-500/40",
  partial: "bg-amber-500/15 text-amber-300 ring-amber-500/40",
};

const DOT_TONE: Record<AnyStatus, string> = {
  pending: "bg-slate-500",
  in_progress: "bg-sky-400 animate-pulse",
  succeeded: "bg-emerald-400",
  failed: "bg-rose-400",
  partial: "bg-amber-400",
};

const CHANNEL_TONE: Record<Channel, string> = {
  email: "bg-violet-500/15 text-violet-300 ring-violet-500/30",
  push: "bg-cyan-500/15 text-cyan-300 ring-cyan-500/30",
};

export function StatusChip({ status }: { status: AnyStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${STATUS_TONE[status]}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

export function StatusDot({ status }: { status: AnyStatus }) {
  return <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${DOT_TONE[status]}`} />;
}

export function ChannelTag({ channel }: { channel: Channel }) {
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] ring-1 ring-inset ${CHANNEL_TONE[channel]}`}
    >
      {channel}
    </span>
  );
}
