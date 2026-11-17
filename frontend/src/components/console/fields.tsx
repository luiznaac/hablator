import { type ReactElement, type ReactNode, cloneElement, useId } from "react";

const inputClass =
  "w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-sky-500 focus:outline-none";

/**
 * A label bound to its control by `htmlFor`/`id` rather than by wrapping it. A wrapping label's
 * accessible name absorbs the control's value, so it would change as the field is typed into.
 */
export function Field({
  label,
  children,
}: { label: string; children: ReactElement<{ id?: string }> }) {
  const id = useId();
  return (
    <div className="block space-y-1">
      <label
        htmlFor={id}
        className="block text-[11px] font-medium uppercase tracking-wide text-slate-500"
      >
        {label}
      </label>
      {cloneElement(children, { id })}
    </div>
  );
}

export function TextInput({
  id,
  value,
  onChange,
  placeholder,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <input
      id={id}
      className={inputClass}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function TextArea({
  id,
  value,
  onChange,
  rows = 4,
  placeholder,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  placeholder?: string;
}) {
  return (
    <textarea
      id={id}
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
      aria-pressed={checked}
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

export function Notice({ tone, children }: { tone: "error" | "success"; children: ReactNode }) {
  const className =
    tone === "error"
      ? "bg-rose-500/10 text-rose-300 ring-rose-500/30"
      : "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30";
  return <p className={`rounded px-2 py-1.5 text-xs ring-1 ring-inset ${className}`}>{children}</p>;
}
