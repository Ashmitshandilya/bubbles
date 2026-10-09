"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { BubblesMascot } from "../BubblesMascot";
import { BTN_PRIMARY, BTN_SECONDARY, Icon, PILL } from "../hub/HubKit";
import { isISODate } from "../../app/lib/cycle-calendar";
import { confidenceCopy, formatRange, nextPeriodLines, ovulationSourceText, shortDay, summarizeLog } from "../../app/lib/cycle-format";
import { NOT_CONTRACEPTION, type DayResponse, type Overview } from "../../app/lib/cycle-types";
import { useCycle } from "./CycleStore";
import { INPUT } from "./fields";
import { PostpartumCard, PregnancyCard } from "./ModeCards";
import { PeriodButtons } from "./PeriodButtons";
import { PhaseRing } from "./PhaseRing";
import { Card, FlagList, InlineError, Notice, PanelError, PanelSkeleton, SafetyAlert, TabHeading } from "./shared";

const CONF_TONE = { learning: "bg-tint-grape text-bubbles-grape-deep", low: "bg-tint-sun text-bubbles-sun-deep", medium: "bg-tint-sky text-bubbles-sky-deep", high: "bg-tint-mint text-bubbles-mint-deep" } as const;

export function TodayTab() {
  const { overview, overviewStatus, overviewError, reloadOverview } = useCycle();
  const [safety, setSafety] = useState<DayResponse["safety"]>(null);

  if (overviewStatus === "loading") return <PanelSkeleton rows={3} />;
  if (!overview) return <PanelError title="Today didn't load" message={overviewError} onRetry={reloadOverview} />;
  if (!overview.has_data) return <EmptyState overview={overview} />;
  return <Loaded o={overview} safety={safety} onSafety={setSafety} />;
}

function EmptyState({ overview }: { overview: Overview }) {
  const { today, postPeriod } = useCycle();
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState(today);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const id = useId();

  async function save() {
    if (!isISODate(date) || date > today) {
      setError("Pick a date up to today.");
      return;
    }
    setBusy(true);
    setError("");
    const result = await postPeriod("start", date === today ? null : date);
    setBusy(false);
    if (!result.ok) setError(result.error);
  }

  return (
    <div className="space-y-5">
      <TabHeading id="cycle-h-today" title="Today" />
      <Card className="text-center">
        <BubblesMascot size={110} mood="caring" className="mx-auto" />
        <h3 className="m-0 mt-3 font-display text-h2 text-ink">Let&apos;s start with your last period</h3>
        <p className="mx-auto mb-0 mt-2 max-w-md text-body text-muted">
          {overview.empty_state ?? "Log the first day of your last period, a past date is fine."} Bubbles learns your rhythm from there and shows ranges, not promises.
        </p>
        {!open ? (
          <button type="button" onClick={() => setOpen(true)} className={`${BTN_PRIMARY} mt-5 min-h-[56px] px-8 text-body`}>
            Log the first day of my last period
          </button>
        ) : (
          <div className="mx-auto mt-5 max-w-xs text-left">
            <label htmlFor={id} className="block text-body-sm font-extrabold text-ink">First day of your last period</label>
            <input id={id} type="date" value={date} max={today} onChange={(e) => e.target.value && setDate(e.target.value)} className={`${INPUT} mt-2`} />
            <div className="mt-3 flex gap-3">
              <button type="button" onClick={save} disabled={busy} className={BTN_PRIMARY}>{busy ? "Saving…" : "Save"}</button>
              <button type="button" onClick={() => setOpen(false)} className={BTN_SECONDARY}>Cancel</button>
            </div>
            {error && <div className="mt-3"><InlineError message={error} /></div>}
          </div>
        )}
        <p className="mx-auto mb-0 mt-4 max-w-md text-body-sm text-muted">Not sure of the exact day? Pick your best guess. You can change it later.</p>
      </Card>
      <Notices notices={overview.notices} />
    </div>
  );
}

function Loaded({ o, safety, onSafety }: { o: Overview; safety: DayResponse["safety"]; onSafety: (s: DayResponse["safety"]) => void }) {
  const { openLog, tempUnit } = useCycle();
  const urgent = o.urgent;
  const calm = !urgent && !safety;
  const mood = o.weather?.tone === "bright" ? "happy" : o.weather?.tone === "heavier" ? "caring" : "calm";
  const conf = confidenceCopy(o.confidence);
  const hideFertility = o.mode === "birth_control";
  const ringLength = Math.round(o.stats.average_length ?? 28);
  const otherFlags = o.flags.filter((f) => f.id !== urgent?.id);
  const summary = summarizeLog(o.today_log, tempUnit);
  const np = o.next_period ? nextPeriodLines(o.next_period) : null;

  return (
    <div className="space-y-5">
      <TabHeading id="cycle-h-today" title="Today" />

      {(urgent || safety) && (
        <div className="space-y-3">
          {safety && <SafetyAlert safety={safety} />}
          {urgent && <FlagList flags={[urgent]} />}
        </div>
      )}

      <Card labelledBy="cycle-now-title">
        <h3 id="cycle-now-title" className="sr-only">Where you are in your cycle</h3>
        <div className="flex flex-wrap items-center gap-6">
          {o.cycle_day !== null && o.mode !== "pregnancy" && (
            <PhaseRing day={o.cycle_day} length={ringLength} phase={o.phase?.id ?? null} phaseLabel={o.phase?.label ?? null} estimated={o.phase?.estimated ?? true} />
          )}
          <div className="min-w-[14rem] flex-1 space-y-3">
            {calm && o.weather && (
              <div className="flex items-start gap-3">
                <BubblesMascot size={64} mood={mood} />
                <div>
                  <p className="m-0 text-body-sm font-extrabold uppercase tracking-wide text-muted">Inner weather · {o.weather.label}</p>
                  <p className="m-0 mt-0.5 font-display text-h4 text-ink">{o.weather.line}</p>
                </div>
              </div>
            )}
            {o.phase && <p className="m-0 text-body text-ink"><strong>{o.phase.label}.</strong> {o.phase.summary}{o.phase.estimated ? " (an estimate)" : ""}</p>}
            {np && (
              <div>
                <p className="m-0 text-body-sm font-extrabold uppercase tracking-wide text-muted">Next period</p>
                <p className="m-0 font-display text-h3 text-ink">{np.range}, {np.likely}</p>
                <p className="m-0 text-body-sm font-bold text-muted">{np.relative}</p>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <span className={`${PILL} ${CONF_TONE[o.confidence]}`}>{conf.label}</span>
              <span className="text-body-sm text-muted">{o.confidence_note || conf.note}</span>
            </div>
          </div>
        </div>

        {!hideFertility && (o.ovulation || o.fertile_window) && (
          <ul className="m-0 mt-4 flex list-none flex-wrap gap-2 p-0">
            {o.fertile_window && (
              <li className={`${PILL} bg-tint-mint text-bubbles-mint-deep`}>
                <span aria-hidden="true">◆</span>
                Fertile window {formatRange(o.fertile_window.start, o.fertile_window.end)}
                {o.fertile_window.active_today ? " · includes today" : o.fertile_window.passed ? " · passed" : ""}
              </li>
            )}
            {o.ovulation && (
              <li className={`${PILL} bg-tint-sun text-bubbles-sun-deep`}>
                <span aria-hidden="true">★</span>
                Ovulation around {shortDay(o.ovulation.date)} ({o.ovulation.confirmed ? "confirmed" : ovulationSourceText(o.ovulation.source)})
              </li>
            )}
          </ul>
        )}
        {o.fertility_note && <p className="m-0 mt-3 text-body-sm text-muted">{o.fertility_note}</p>}
        {o.pms && (
          <p className="m-0 mt-3 rounded-2xl bg-tint-grape px-4 py-3 text-body-sm font-bold text-bubbles-grape-deep">
            PMS hint · {o.pms.text}{o.pms.personal ? "" : " This is a general window, not learned from your logs yet."}
          </p>
        )}
      </Card>

      {otherFlags.length > 0 && <FlagList flags={otherFlags} />}

      {o.mode !== "pregnancy" && (
        <Card labelledBy="cycle-period-title">
          <h3 id="cycle-period-title" className="m-0 mb-3 font-display text-h3 text-ink">Your period</h3>
          <PeriodButtons onResult={(r) => onSafety(r.safety)} />
        </Card>
      )}

      {o.pregnancy && <PregnancyCard info={o.pregnancy} />}
      {o.postpartum && <PostpartumCard info={o.postpartum} />}

      <Card labelledBy="cycle-log-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 id="cycle-log-title" className="m-0 font-display text-h3 text-ink">Today&apos;s log</h3>
          <button type="button" onClick={() => openLog()} className={BTN_SECONDARY}>{summary.length ? "Edit today" : "Log today"}</button>
        </div>
        {summary.length ? (
          <ul className="m-0 mt-3 flex list-none flex-wrap gap-2 p-0">
            {summary.map((s) => <li key={s} className={`${PILL} bg-blush text-ink-soft border border-line`}>{s}</li>)}
          </ul>
        ) : (
          <p className="m-0 mt-2 text-body text-muted">Nothing logged yet today. A quick note on how you feel helps Bubbles learn.</p>
        )}
      </Card>

      <Notices notices={o.notices} />

      <Link href="/companion" className="bubbles-press inline-flex min-h-[44px] items-center gap-2 rounded-full border-2 border-line bg-surface px-5 text-body-sm font-extrabold text-bubbles-grape-deep no-underline hover:border-line-strong">
        <Icon id="sparkle" size={18} /> Ask Bubbles about your cycle
      </Link>
    </div>
  );
}

function Notices({ notices }: { notices: string[] }) {
  const list = notices.length ? notices : [NOT_CONTRACEPTION];
  return (
    <div className="space-y-2">
      {list.map((n) => <Notice key={n} tone="sky">{n}</Notice>)}
    </div>
  );
}
