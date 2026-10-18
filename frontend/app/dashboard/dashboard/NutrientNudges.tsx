"use client";

import Link from "next/link";
import { LEVEL_TEXT, type Nudge } from "../../lib/nutrients";

/** The inside of the closed "Blood test ideas" row on Today. Every sentence is the server's; gaps are listed as gaps. */
export function NutrientNudges({ items }: { items: Nudge[] }) {
  return (
    <>
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {items.map((n) => (
          <li key={n.id} data-private className="flex flex-col gap-2 rounded-[20px] border border-line bg-blush p-4">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="m-0 text-base font-bold leading-snug">{n.headline}</h3>
              <span className="rounded-full bg-tint-grape px-2.5 py-1 text-xs font-extrabold text-bubbles-grape-deep">{LEVEL_TEXT[n.level]}</span>
            </div>
            {n.reasons.length > 0 && (
              <ul className="m-0 list-disc pl-5 text-sm leading-relaxed text-ink-soft">
                {n.reasons.map((r) => <li key={r}>{r}</li>)}
              </ul>
            )}
            {n.gaps.map((g) => <p key={g} className="m-0 text-sm font-semibold text-ink-soft">Gap: {g}</p>)}
            {n.ask && <p className="m-0 text-sm font-bold leading-relaxed">{n.ask}</p>}
          </li>
        ))}
      </ul>
      <Link href="/labs" className="inline-flex min-h-[44px] items-center self-start text-sm font-extrabold text-bubbles-pink-ink">Add a lab result</Link>
    </>
  );
}
