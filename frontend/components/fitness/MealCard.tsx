"use client";

import { whyForMeal, mealItemsText } from "../../app/lib/fitness-calc";
import type { PlanMeal } from "../../app/lib/fitness-types";
import { BTN_SECONDARY, CARD } from "../hub/HubKit";
import { RangeBadge } from "./ui";

/** One planned meal: what is in it, why it is there, and the two things you can do with it. */
export function MealCard({ meal, onSwap, onLog, logging = false, compact = false }: {
  meal: PlanMeal; onSwap?: () => void; onLog?: () => void; logging?: boolean; compact?: boolean;
}) {
  const why = whyForMeal(meal);
  return (
    <article className={`${CARD} flex flex-col gap-3 p-4 sm:p-5`} aria-label={`${meal.label}: ${meal.name}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="m-0 text-label font-extrabold uppercase tracking-wide text-subtle">{meal.label}</p>
          <h3 className="m-0 font-display text-h3 text-ink">{meal.name}</h3>
        </div>
        <div className="text-right">
          <RangeBadge value={meal.totals.kcal} low={meal.totals.kcal_low} high={meal.totals.kcal_high} />
          <p className="m-0 text-body-sm text-muted">{Math.round(meal.totals.protein_g)} g protein</p>
        </div>
      </div>
      {!compact && (
        <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-body-sm text-ink-soft">
          {meal.items.map((i, n) => (
            <li key={`${i.food}-${n}`}>
              {Math.round(i.grams)} g {i.food}
            </li>
          ))}
        </ul>
      )}
      {why && <p className="m-0 text-body-sm text-muted">{why}</p>}
      {(onSwap || onLog) && (
        <div className="flex flex-wrap gap-2">
          {onSwap && (
            <button type="button" onClick={onSwap} className={BTN_SECONDARY} aria-label={`Swap ${meal.label}: ${meal.name}`}>
              Swap
            </button>
          )}
          {onLog && (
            <button type="button" onClick={onLog} disabled={logging} className={BTN_SECONDARY} aria-label={`Log ${meal.label}: ${meal.name}`}>
              {logging ? "Checking…" : "Log this meal"}
            </button>
          )}
        </div>
      )}
      <span className="sr-only">{mealItemsText(meal.items)}</span>
    </article>
  );
}
