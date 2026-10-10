"use client";

import { BTN_SECONDARY, PILL } from "../hub/HubKit";
import { formatRange, formatTemp, longDay, ovulationSourceText } from "../../app/lib/cycle-format";
import { NOT_CONTRACEPTION, type Article } from "../../app/lib/cycle-types";
import { useCycle } from "./CycleStore";
import { EducationSection } from "./Education";
import { Card, Notice, PanelError, PanelSkeleton, TabHeading } from "./shared";

const isOvulationArticle = (a: Article) => /ovulation|lh|opk/i.test(`${a.id} ${a.title} ${a.tags.join(" ")}`);

export function FertilityTab() {
  const { overview, overviewStatus, overviewError, reloadOverview, openLog, tempUnit } = useCycle();
  if (overviewStatus === "loading") return <PanelSkeleton rows={3} />;
  if (!overview) return <PanelError title="Fertility didn't load" message={overviewError} onRetry={reloadOverview} />;

  const o = overview;
  const bbt = o.today_log?.bbt_c ?? null;
  const birthControl = o.mode === "birth_control";

  return (
    <div className="space-y-5">
      <TabHeading id="cycle-h-fertility" title="Fertility">Estimates of your fertile window and ovulation, drawn from your own logs.</TabHeading>

      <Notice tone="sun" title="Not birth control">{NOT_CONTRACEPTION}</Notice>

      {birthControl ? (
        <Card labelledBy="cycle-bc-title">
          <h3 id="cycle-bc-title" className="m-0 font-display text-h3 text-ink">Why ovulation estimates are hidden</h3>
          <p className="m-0 mt-2 text-body text-ink">
            {o.fertility_note ?? "Hormonal birth control changes ovulation and bleeding, so a fertile-window estimate from your logs would not be reliable. Bubbles keeps it hidden while you are in this mode."}
          </p>
        </Card>
      ) : (
        <div className="grid gap-5 md:grid-cols-2">
          <Card labelledBy="cycle-ov-title">
            <h3 id="cycle-ov-title" className="m-0 font-display text-h3 text-ink">Ovulation</h3>
            {o.ovulation ? (
              <>
                <p className="m-0 mt-2 font-display text-metric text-ink">Around {longDay(o.ovulation.date)}</p>
                <p className="m-0 text-body-sm font-bold text-muted">Could be between {formatRange(o.ovulation.earliest, o.ovulation.latest)}</p>
                <p className="m-0 mt-2 flex flex-wrap items-center gap-2 text-body-sm text-ink">
                  <span className={`${PILL} ${o.ovulation.confirmed ? "bg-tint-mint text-bubbles-mint-deep" : "bg-tint-sun text-bubbles-sun-deep"}`}>
                    {o.ovulation.confirmed ? "✓ Confirmed by your logs" : "Estimate"}
                  </span>
                  {ovulationSourceText(o.ovulation.source)}
                  {o.ovulation.passed ? " · already passed" : ""}
                </p>
              </>
            ) : (
              <p className="m-0 mt-2 text-body text-muted">No estimate yet. Log a few cycles, and optionally ovulation tests or temperatures, and Bubbles will offer a range.</p>
            )}
          </Card>
          <Card labelledBy="cycle-fw-title">
            <h3 id="cycle-fw-title" className="m-0 font-display text-h3 text-ink">Fertile window</h3>
            {o.fertile_window ? (
              <>
                <p className="m-0 mt-2 font-display text-metric text-ink">{formatRange(o.fertile_window.start, o.fertile_window.end)}</p>
                <p className="m-0 text-body-sm font-bold text-muted">Could start as early as {formatRange(o.fertile_window.earliest, o.fertile_window.earliest)} and end as late as {formatRange(o.fertile_window.latest, o.fertile_window.latest)}</p>
                <p className="m-0 mt-2 text-body-sm text-ink">
                  {o.fertile_window.active_today ? "Your estimated window includes today." : o.fertile_window.passed ? "This estimated window has passed." : "This window is still ahead."}
                </p>
              </>
            ) : (
              <p className="m-0 mt-2 text-body text-muted">No estimate yet.</p>
            )}
          </Card>
        </div>
      )}
      {!birthControl && o.fertility_note && <p className="m-0 text-body-sm text-muted">{o.fertility_note}</p>}

      <Card labelledBy="cycle-bbt-title">
        <h3 id="cycle-bbt-title" className="m-0 font-display text-h3 text-ink">Basal body temperature</h3>
        <p className="m-0 mt-2 text-body text-ink">
          Your resting temperature is often slightly higher after ovulation. Taking it each morning, before you get up, can help show a pattern over a few cycles.
          One reading on its own says little.
        </p>
        <p className="m-0 mt-3 text-body font-bold text-ink">
          {bbt !== null ? `Today you logged ${formatTemp(bbt, tempUnit)}.` : "No temperature logged today."}
        </p>
        <button type="button" onClick={() => openLog()} className={`${BTN_SECONDARY} mt-3`}>Log your temperature</button>
      </Card>

      {!birthControl && <EducationSection mode={o.mode} title="About ovulation tests" filter={isOvulationArticle} emptyText="No ovulation test articles for this mode." />}
    </div>
  );
}
