"use client";

import { useCallback, useEffect, useState } from "react";
import type { PlanDay, PlanMeal } from "../../app/lib/fitness-types";
import { BTN_PRIMARY, ErrorCard, Skeleton } from "../hub/HubKit";
import { RangeBadge, Sheet, useSend } from "./ui";

/** Alternatives for one meal slot (server-vetted for the diet style and allergies). Nothing changes until "Use this". */
export function SwapSheet({ open, onClose, day, meal, onSwapped }: {
  open: boolean; onClose: () => void; day: number; meal: PlanMeal | null; onSwapped: (day: PlanDay) => void;
}) {
  const send = useSend();
  const [options, setOptions] = useState<PlanMeal[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const slot = meal?.slot;

  const load = useCallback(async () => {
    if (!slot) return;
    setOptions(null);
    setError(null);
    const r = await send<{ options: PlanMeal[] }>("/fitness/diet/swap-options", "POST", { day, slot });
    if (r.ok) setOptions(r.data.options);
    else setError(r.message);
  }, [send, day, slot]);

  useEffect(() => {
    if (open) {
      setNote(null);
      void load();
    }
  }, [open, load]);

  async function choose(o: PlanMeal) {
    if (!slot || busy) return;
    setBusy(o.template_id);
    setNote(null);
    const r = await send<{ day: PlanDay }>("/fitness/diet/swap", "POST", { day, slot, template_id: o.template_id });
    setBusy(null);
    if (r.ok) {
      onSwapped(r.data.day);
      onClose();
    } else setNote(r.message);
  }

  return (
    <Sheet open={open} onClose={onClose} title={meal ? `Swap ${meal.label.toLowerCase()}` : "Swap meal"}>
      <p className="m-0 text-body-sm text-muted">These fit your diet style and allergies. Pick one and Bubbles rebalances the rest of the day.</p>
      <div aria-live="polite">
        {note && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{note}</p>}
      </div>
      {error ? (
        <ErrorCard inset title="Couldn't load swaps" message={error} onRetry={() => void load()} />
      ) : !options ? (
        <div className="flex flex-col gap-3" role="status" aria-label="Loading swaps">
          <Skeleton className="h-20 w-full rounded-3xl" />
          <Skeleton className="h-20 w-full rounded-3xl" />
        </div>
      ) : options.length === 0 ? (
        <p className="m-0 rounded-2xl bg-blush p-4 text-body-sm text-muted">No other meals fit this slot right now. Try regenerating the plan with different foods.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {options.map((o) => (
            <li key={o.template_id} className="rounded-3xl border border-line p-4">
              <p className="m-0 font-display text-h4 text-ink">{o.name}</p>
              <p className="m-0 mt-1 text-body-sm text-muted">
                <RangeBadge value={o.totals.kcal} low={o.totals.kcal_low} high={o.totals.kcal_high} /> · {Math.round(o.totals.protein_g)} g protein
              </p>
              <p className="m-0 mt-1 text-body-sm text-ink-soft">{o.items.map((i) => `${Math.round(i.grams)} g ${i.food}`).join(", ")}</p>
              <button type="button" onClick={() => void choose(o)} disabled={busy !== null} className={`${BTN_PRIMARY} mt-3`} aria-label={`Use ${o.name}`}>
                {busy === o.template_id ? "Swapping…" : "Use this"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}
