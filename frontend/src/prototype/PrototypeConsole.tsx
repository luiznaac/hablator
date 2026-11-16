// PROTOTYPE (issue #19) — three structurally different shapes of the hub debug console, on this
// throwaway /prototype route, switchable with ?variant=A|B|C or the ← → keys. In-memory fixtures
// only; the winning shape is rewritten properly in the real page, never folded in as-is.

import { useSearchParams } from "react-router-dom";
import { PrototypeSwitcher, VARIANTS, type VariantKey } from "./Switcher.tsx";
import { VariantA } from "./VariantA.tsx";
import { VariantB } from "./VariantB.tsx";
import { VariantC } from "./VariantC.tsx";
import { usePrototypeStore } from "./store.ts";

export function PrototypeConsole() {
  const [params] = useSearchParams();
  const requested = params.get("variant")?.toUpperCase();
  const variant: VariantKey = VARIANTS.some((entry) => entry.key === requested)
    ? (requested as VariantKey)
    : "A";
  const store = usePrototypeStore();

  return (
    <>
      <div className="bg-amber-400 px-4 py-1 text-center text-[11px] font-medium text-amber-950">
        PROTOTYPE — in-memory fixtures, no backend · switch with ?variant=A|B|C or ← →
      </div>
      {variant === "A" && <VariantA store={store} />}
      {variant === "B" && <VariantB store={store} />}
      {variant === "C" && <VariantC store={store} />}
      <PrototypeSwitcher current={variant} />
    </>
  );
}
