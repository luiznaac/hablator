// PROTOTYPE — the floating variant switcher for the debug-UI shape prototype (issue #19).
// Hidden in production builds so a stray merge cannot ship it.

import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

export const VARIANTS = [
  { key: "A", name: "Three-pane console" },
  { key: "B", name: "Timeline + drawer" },
  { key: "C", name: "Table + inspector" },
] as const;

export type VariantKey = (typeof VARIANTS)[number]["key"];

export function PrototypeSwitcher({ current }: { current: VariantKey }) {
  const [, setSearchParams] = useSearchParams();
  const index = VARIANTS.findIndex((variant) => variant.key === current);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable === true;
      if (typing) return;
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      const delta = event.key === "ArrowLeft" ? -1 : 1;
      const next = VARIANTS[(index + delta + VARIANTS.length) % VARIANTS.length];
      setSearchParams(
        (previous) => {
          const params = new URLSearchParams(previous);
          params.set("variant", next.key);
          return params;
        },
        { replace: true },
      );
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [index, setSearchParams]);

  if (import.meta.env.PROD) return null;

  const move = (delta: number) => {
    const next = VARIANTS[(index + delta + VARIANTS.length) % VARIANTS.length];
    setSearchParams(
      (previous) => {
        const params = new URLSearchParams(previous);
        params.set("variant", next.key);
        return params;
      },
      { replace: true },
    );
  };

  const variant = VARIANTS[index];

  return (
    <div className="fixed bottom-5 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-full bg-white px-2 py-1.5 text-slate-900 shadow-xl ring-1 ring-black/10">
      <button
        type="button"
        aria-label="Previous variant"
        onClick={() => move(-1)}
        className="rounded-full px-2 py-0.5 text-lg leading-none hover:bg-slate-200"
      >
        ←
      </button>
      <span className="text-xs font-semibold">
        {variant.key} · {variant.name}
      </span>
      <button
        type="button"
        aria-label="Next variant"
        onClick={() => move(1)}
        className="rounded-full px-2 py-0.5 text-lg leading-none hover:bg-slate-200"
      >
        →
      </button>
      <span className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white">
        prototype
      </span>
    </div>
  );
}
