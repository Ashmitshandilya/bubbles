"use client";

// Sleep insight panels: score + breakdown, regularity / debt / streak, goal editor, tag patterns, wind-down, weekday chart.
// Wording rules: patterns are "tends to", never a cause; debt is described gently; missing data is a gap, never zero.

import { useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, PILL } from "../../components/hub/HubKit";
import { Stepper } from "../../components/tracking/kit";
import { ScoreRing, WeekdayChart } from "../../components/wellness/charts";
import { EmptyNote, ErrorNotice, LiveRegion, MeterRow, Notice, Panel, QueryView, Switch, TimeField } from "../../components/wellness/ui";
import { useWellnessQuery, useWellnessSend } from "../../components/wellness/useWellness";
import { formatHours, formatMinutes, plural } from "../../app/lib/wellness-format";
import type { NotificationSettingsResponse, SleepGoal, SleepOverview } from "../../app/lib/wellness-types";
import Link from "next/link";

const PART_WORDS: Record<string, { label: string; caption: string }> = {
  duration: { label: "Hours", caption: "how close your average is to your goal" },
  regularity: { label: "Regular times", caption: "how steady your bed and wake times are" },
  quality: { label: "How rested", caption: "how rested you said you felt" },
};

export function ScorePanel({ overview }: { overview: SleepOverview }) {
  const { score, nights_logged } = overview;
  if (!score) {
    return (
      <Panel title="Your sleep score" kicker="Last 30 days">
        <EmptyNote title={nights_logged === 0 ? "No nights logged yet" : "Not enough to score yet"}>
          <p className="m-0">{overview.data_gaps[0] ?? "Log a night and Bubbles will start to see your rhythm."}</p>
          <p className="m-0 mt-1">The score blends hours slept, how regular your times are and how rested you feel. Parts you haven&apos;t logged are left out, not counted as zero.</p>
        </EmptyNote>
      </Panel>
    );
  }
  const parts = Object.entries(score.parts);
  const missing = Object.keys(PART_WORDS).filter((k) => !(k in score.parts));
  return (
    <Panel title="Your sleep score" kicker={`Last ${overview.window_days} days · ${plural(nights_logged, "night")} logged`}>
      <div className="flex flex-wrap items-center gap-6">
        <ScoreRing value={score.value} label={score.label} />
        <ul className="m-0 flex min-w-[14rem] flex-1 list-none flex-col gap-3 p-0" aria-label="What the score is made of">
          {parts.map(([key, value]) => (
            <MeterRow key={key} label={PART_WORDS[key]?.label ?? key} value={value} signal="grape" caption={`${value} / 100`} />
          ))}
        </ul>
      </div>
      <ul className="m-0 list-disc space-y-1 pl-5 text-body-sm text-muted">
        {parts.map(([key]) => (
          <li key={key}>
            <strong className="text-ink">{PART_WORDS[key]?.label ?? key}:</strong> {PART_WORDS[key]?.caption ?? ""}
          </li>
        ))}
        {missing.map((key) => (
          <li key={key}>
            <strong className="text-ink">{PART_WORDS[key].label}:</strong> not counted yet (no data), so the rest carry more weight.
          </li>
        ))}
      </ul>
      <p className="m-0 text-body-sm text-muted">A snapshot of your own logs to help you notice patterns. It is not a medical measure.</p>
    </Panel>
  );
}

export function RhythmPanel({ overview }: { overview: SleepOverview }) {
  const { regularity, debt, streak, last_night: last, average_hours: avg, goal } = overview;
  return (
    <Panel title="Your rhythm" kicker="Regularity, debt and streak">
      <dl className="m-0 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Last night" value={last ? formatHours(last.hours) : null} note={last?.score != null ? `score ${last.score}` : undefined} />
        <Stat label="Average" value={avg != null ? formatHours(avg) : null} note={`goal ${formatHours(goal.hours)}`} />
        <Stat label="Bed and wake times" value={regularity ? `±${regularity.minutes} min` : null} gap="A few more nights" note={regularity ? (regularity.basis === "times" ? "usual swing" : "swing in hours slept") : undefined} />
        <Stat label="This week vs goal" value={debt ? (debt.hours < 1 ? "Close" : `${debt.hours} h under`) : null} note={debt?.partial ? `from ${plural(debt.nights_logged, "night")} so far` : undefined} />
      </dl>
      <ul className="m-0 flex list-none flex-col gap-2 p-0 text-body-sm text-ink-soft">
        {regularity && (
          <li>
            {regularity.consistent
              ? "Your bed and wake times have been fairly steady, which tends to make sleep feel easier."
              : "Your bed and wake times move around a bit. A similar time most nights can help, but only when it suits your life."}
            {regularity.basis === "duration" && " Add bedtime and wake time to your logs for a closer look."}
          </li>
        )}
        {debt && <li>{debt.message}</li>}
        <li>{streak.message}</li>
      </ul>
      <p className="m-0 text-body-sm text-muted">Naps are shown separately and aren&apos;t counted in your score or debt. {overview.naps.total_minutes > 0 && `You logged ${formatMinutes(overview.naps.total_minutes)} of naps across ${plural(overview.naps.days_with_naps, "day")}.`}</p>
    </Panel>
  );
}

function Stat({ label, value, note, gap }: { label: string; value: string | null; note?: string; gap?: string }) {
  return (
    <div className={`flex min-w-0 flex-col gap-1 rounded-[20px] border-2 bg-surface p-3 ${value === null ? "border-dashed border-[#C9BCFF]" : "border-[#E4DCFF]"}`}>
      <dt className="text-body-sm font-extrabold text-bubbles-grape-deep">{label}</dt>
      <dd className="m-0 break-words">
        {value === null ? <span className="font-display text-h4 text-muted">{gap ?? "Not logged yet"}</span> : <span className="font-display text-metric text-default">{value}</span>}
      </dd>
      {note && <dd className="m-0 text-body-sm font-semibold text-muted">{note}</dd>}
    </div>
  );
}

/* ── Goal editor ────────────────────────────────────────────────────── */

export function GoalEditor({ goal, onSaved }: { goal: SleepGoal; onSaved: () => void }) {
  const send = useWellnessSend();
  const [hours, setHours] = useState(String(goal.hours));
  const [bedtime, setBedtime] = useState(goal.bedtime ?? "");
  const [wake, setWake] = useState(goal.wake_time ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  async function save() {
    const h = Number(hours);
    if (!hours.trim() || !Number.isFinite(h) || h < 4 || h > 12) {
      setError("Choose a goal between 4 and 12 hours.");
      return;
    }
    setBusy(true);
    setError("");
    setSaved("");
    const result = await send("/wellness/sleep/goal", "POST", { hours: h, ...(bedtime ? { bedtime } : {}), ...(wake ? { wake_time: wake } : {}) });
    setBusy(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    setSaved("Goal saved.");
    onSaved();
  }

  return (
    <Panel title="Your sleep goal" kicker={goal.source === "you" ? "Set by you" : "Suggested for your age"}>
      <p className="m-0 text-body-sm text-muted">
        A common range for your age group is {goal.recommended_min} to {goal.recommended_max} hours. Your goal is yours to choose; a bedtime and wake time are optional and help Bubbles time your wind-down.
      </p>
      <Stepper id="goal-hours" label="Hours a night" value={hours} onChange={setHours} min={4} max={12} step={0.25} unit="h" fallback={goal.hours} signal="grape" />
      <div className="grid gap-4 sm:grid-cols-2">
        <TimeField id="goal-bed" label="Usual bedtime" value={bedtime} onChange={setBedtime} optional />
        <TimeField id="goal-wake" label="Usual wake time" value={wake} onChange={setWake} optional />
      </div>
      {error && <ErrorNotice message={error} />}
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => void save()} disabled={busy} className={BTN_PRIMARY}>
          {busy ? "Saving…" : "Save goal"}
        </button>
        <LiveRegion message={saved} />
        {saved && <span className="text-body-sm font-extrabold text-bubbles-mint-deep">{saved}</span>}
      </div>
    </Panel>
  );
}

/* ── Insights ───────────────────────────────────────────────────────── */

export function InsightsPanel({ overview }: { overview: SleepOverview }) {
  return (
    <Panel title="Patterns in your sleep" kicker="Your own logs, not proof of a cause">
      {overview.insights.length === 0 ? (
        <EmptyNote title="Not enough tagged nights yet">
          {overview.data_gaps.length ? overview.data_gaps.map((g) => <p key={g} className="m-0">{g}</p>) : <p className="m-0">Tag a few nights (caffeine, screens, stress…) and patterns can show up here.</p>}
          <p className="m-0 mt-1">Bubbles only shares a pattern when there are enough nights both with and without a tag, so it isn&apos;t reading too much into a few days.</p>
        </EmptyNote>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {overview.insights.map((i) => (
            <li key={i.tag} className="rounded-2xl bg-blush px-4 py-3">
              <p className="m-0 text-body font-bold text-ink">{i.text}</p>
              <p className="m-0 mt-2 flex flex-wrap items-center gap-2 text-body-sm text-muted">
                <span className={`${PILL} ${i.confidence === "moderate" ? "bg-tint-grape text-bubbles-grape-deep" : "bg-tint-sun text-bubbles-sun-deep"}`}>
                  {i.confidence === "moderate" ? "A steadier pattern" : "An early pattern"}
                </span>
                {i.with_n} nights with it, {i.without_n} without
              </p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/* ── Wind-down ──────────────────────────────────────────────────────── */

export function WinddownPanel({ overview }: { overview: SleepOverview }) {
  const [settings, reload] = useWellnessQuery<NotificationSettingsResponse>("/notifications/settings", { tz: false });
  const send = useWellnessSend();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [said, setSaid] = useState("");

  async function toggle(next: boolean) {
    setBusy(true);
    setError("");
    const result = await send("/notifications/settings", "PUT", { types: { winddown: next } }, { tz: false });
    setBusy(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    setSaid(next ? "Wind-down reminders are on." : "Wind-down reminders are off.");
    reload();
  }

  return (
    <Panel title="Wind-down" kicker="A gentle evening nudge">
      <p className="m-0 text-body text-ink">{overview.winddown.message}</p>
      <p className="m-0 text-body-sm text-muted">
        Suggested bedtime {overview.winddown.bedtime}, wind-down from {overview.winddown.winddown}. Reminders stay quiet during your quiet hours and never include health details.
      </p>
      <QueryView query={settings} onRetry={reload} what="reminder settings" skeleton={<div className="bubbles-skeleton h-16 rounded-2xl" aria-hidden="true" />}>
        {(data) => (
          <>
            <Switch
              label="Remind me to wind down"
              hint={data.settings.channels.in_app ? "Shows up in your Bubbles notifications." : "In-app notifications are off in Settings, so nothing would show."}
              checked={data.settings.types.winddown}
              disabled={busy}
              onChange={(v) => void toggle(v)}
            />
            <LiveRegion message={said} />
          </>
        )}
      </QueryView>
      {error && <ErrorNotice message={error} />}
      <Link href="/settings" className={`${BTN_SECONDARY} no-underline`}>
        Reminder settings
      </Link>
    </Panel>
  );
}

export function WeekdayPanel({ overview }: { overview: SleepOverview }) {
  return (
    <Panel title="Your week" kicker="Average hours by weekday">
      {overview.weekday && <Notice tone="calm">{overview.weekday.message}</Notice>}
      <WeekdayChart series={overview.series} goalHours={overview.goal.hours} />
    </Panel>
  );
}

