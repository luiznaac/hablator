// PROTOTYPE — shared form controls for the debug-UI shape prototype (issue #19).

import type { ReactNode } from "react";
import type { SubmitState } from "./compose.ts";

const inputClass =
  "w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-sky-500 focus:outline-none";

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    // biome-ignore lint/a11y/noLabelWithoutControl: the control arrives as `children`; Biome cannot see through it.
    <label className="block space-y-1">
      <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
        {label}
      </span>
      {children}
    </label>
  );
}

export function TextInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <input
      className={inputClass}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function TextArea({
  value,
  onChange,
  rows = 4,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  placeholder?: string;
}) {
  return (
    <textarea
      className={`${inputClass} resize-y`}
      rows={rows}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function ChannelToggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`rounded px-2 py-1 text-xs ring-1 ring-inset ${
        checked
          ? "bg-sky-500/20 text-sky-200 ring-sky-500/50"
          : "bg-slate-900 text-slate-400 ring-slate-700"
      }`}
    >
      {label}
    </button>
  );
}

export function SubmitNote({ state }: { state: SubmitState }) {
  if (state.status === "error") {
    return (
      <p className="rounded bg-rose-500/10 px-2 py-1.5 text-xs text-rose-300 ring-1 ring-rose-500/30">
        {state.message}
      </p>
    );
  }
  if (state.status === "sent") {
    return (
      <p className="rounded bg-emerald-500/10 px-2 py-1.5 text-xs text-emerald-300 ring-1 ring-emerald-500/30">
        {state.message}
      </p>
    );
  }
  if (state.status === "sending") return <p className="text-xs text-slate-500">sending…</p>;
  return null;
}
