"use client";

import { Icon, SectionHeading } from "./TodaySections";
import type { WeekRecap } from "./recap";

// The three highlight bubbles borrow the signal colours; they carry no meaning, so they never read as good or bad.
const BUBBLE = ["bg-tint-pink text-bubbles-pink-deep", "bg-tint-grape text-bubbles-grape-deep", "bg-tint-sky text-bubbles-sky-deep"] as const;

/**
 * "Your week" on Today. Shows nothing at all when the weekly call fails or cannot say how much was recorded, so a
 * missing recap never reads as an error or as a quiet week.
 */
export function WeekRecapCard({ state, recap }: { state: "loading" | "error" | "ready"; recap: WeekRecap | null }) {
  if (state === "error" || (state === "ready" && !recap)) return null;
  if (state === "loading" || !recap) return <div className="bubbles-skeleton h-[220px] rounded-[28px]" aria-label="Loading your week" />;

  return (
    <section aria-labelledby="today-week-recap" className="relative flex flex-col gap-5 overflow-hidden rounded-[28px] border-2 border-line bg-surface p-5 sm:p-7">
      <span aria-hidden="true" className="pointer-events-none absolute -left-14 -top-14 h-40 w-40 rounded-full bg-tint-grape opacity-70" />
      <div className="relative flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <SectionHeading id="today-week-recap">Your week</SectionHeading>
        <span className="text-[0.8125rem] font-bold text-ink-soft">The last 7 days, from what Bubbles recorded</span>
      </div>

      <div className="relative grid items-start gap-4 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] md:gap-6">
        {recap.highlights.length > 0 && (
          <ul data-private className="bubbles-stagger m-0 flex list-none flex-col gap-3 p-0">
            {recap.highlights.map((line, index) => (
              <li key={`${index}-${line}`} className="flex items-start gap-3">
                <span aria-hidden="true" className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${BUBBLE[index % BUBBLE.length]}`}>
                  <Icon name="sparkle" size={16} />
                </span>
                <span className="min-w-0 pt-1 text-base font-semibold leading-snug">{line}</span>
              </li>
            ))}
          </ul>
        )}

        <div className={`flex flex-col gap-3 ${recap.highlights.length === 0 ? "md:col-span-2" : ""}`}>
          <div className="flex flex-col gap-1 rounded-[20px] border-2 border-dashed border-[#9FD3FF] p-4">
            <span className="text-label font-extrabold text-bubbles-sky-deep">A gap</span>
            <p data-private className="m-0 text-[0.9375rem] leading-relaxed text-ink">{recap.gap}</p>
          </div>
          <div className="flex flex-col gap-1 rounded-[20px] bg-tint-mint p-4">
            <span className="text-label font-extrabold text-bubbles-mint-deep">Try this next week</span>
            <p className="m-0 text-[0.9375rem] leading-relaxed text-ink">{recap.tryNext}</p>
          </div>
        </div>
      </div>

      <p className="relative m-0 text-[0.8125rem] font-semibold leading-relaxed text-ink-soft">{recap.disclaimer}</p>
    </section>
  );
}
