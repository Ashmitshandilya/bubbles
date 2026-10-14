"use client";

import { useState } from "react";
import Link from "next/link";
import { Skeleton, PILL } from "../../components/hub/HubKit";
import { Choices, Disclaimer, EmptyState, EntryRow, History, LogButton, LogSheet, SavedToast, Stepper, TrackerHero, TrackerShell } from "../../components/tracking/kit";
import { toNumber, useTracker, type Entry } from "../../components/tracking/data";
import { GardenScene } from "../../components/wellness/charts";
import { ErrorNotice, LiveRegion, Notice, Panel, QueryView } from "../../components/wellness/ui";
import { useWellnessQuery, useWellnessSend } from "../../components/wellness/useWellness";
import { BEVERAGE_ORDER, beverageLabel, formatMl, loggedMessage, plural, reminderHint } from "../../app/lib/wellness-format";
import type { HydrationOverview } from "../../app/lib/wellness-types";

export function HydrationClient() {
  return (
    <TrackerShell title="Hydration">
      <Hydration />
    </TrackerShell>
  );
}

function Hydration() {
  const [overview, reload] = useWellnessQuery<HydrationOverview>("/wellness/hydration/overview");
  const history = useTracker("/health/hydration", 30);
  const send = useWellnessSend();

  const [type, setType] = useState("water");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [customMl, setCustomMl] = useState("");
  const [customError, setCustomError] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);

  /** One drink. Resolves null on success or the message to show; also used by the custom sheet. */
  async function add(body: { preset?: string; ml?: number }, key: string): Promise<string | null> {
    setBusy(key);
    setError("");
    const result = await send<HydrationOverview>("/wellness/hydration/log", "POST", { ...body, type });
    setBusy(null);
    if (!result.ok) {
      setError(result.message);
      return result.message;
    }
    const d = result.data;
    const logged = d.logged;
    const base = logged ? loggedMessage(logged.ml, logged.type, logged.hydrating_ml) : "Drink added.";
    const progress = d.goal?.goal_ml != null ? ` ${formatMl(d.effective_ml)} of ${formatMl(d.goal.goal_ml)} so far today.` : ` ${formatMl(d.raw_ml)} logged today.`;
    setMessage(base + progress);
    setSavedAt(`${Date.now()}`);
    reload();
    history.retry();
    return null;
  }

  async function submitCustom(): Promise<string | null | false> {
    const n = Number(customMl);
    if (!customMl.trim() || !Number.isFinite(n) || n < 10 || n > 2000) {
      setCustomError("Choose an amount between 10 ml and 2,000 ml.");
      return false;
    }
    setCustomError("");
    const failure = await add({ ml: Math.round(n) }, "custom");
    if (!failure) setCustomMl("");
    return failure;
  }

  const factors = overview.status === "ready" ? overview.data.beverage_factors : {};
  const types = (Object.keys(factors).length ? BEVERAGE_ORDER.filter((t) => t in factors).concat(Object.keys(factors).filter((t) => !BEVERAGE_ORDER.includes(t))) : BEVERAGE_ORDER)
    .map((t) => ({ value: t, label: beverageLabel(t) }));
  const factor = factors[type];
  const factorHint = factor === undefined ? undefined : factor <= 0 ? `${beverageLabel(type)} doesn't count toward your drinks target.` : factor < 1 ? `${beverageLabel(type)} counts for about ${Math.round(factor * 100)}% toward your target.` : undefined;

  return (
    <>
      <TrackerHero
        signal="sky"
        icon="hydration"
        kicker="WATER INTAKE"
        title="Hydration"
        why="Water links to your energy, headaches and workouts. Quick sips help Bubbles spot those patterns."
        action={<LogButton signal="sky" onClick={() => { setCustomError(""); setOpen(true); }}>Add a drink</LogButton>}
      />

      <QueryView
        query={overview}
        onRetry={reload}
        what="today's water"
        skeleton={<div className="flex flex-col gap-6"><Skeleton className="h-72 rounded-3xl" /><Skeleton className="h-40 rounded-3xl" /></div>}
      >
        {(o) => (
          <>
            <TodayPanel o={o} />

            <Panel title="Add a drink" kicker="One tap">
              <Choices id="drink-type" legend="What are you drinking?" options={types} value={type} onChange={(v) => v && setType(v)} signal="sky" allowDeselect={false} hint={factorHint} />
              <div role="group" aria-label="Amount" className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {o.presets.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    disabled={busy !== null}
                    onClick={() => void add({ preset: p.id }, p.id)}
                    className="bubbles-press flex min-h-[64px] flex-col items-center justify-center rounded-2xl border-2 border-bubbles-sky-deep bg-tint-sky px-3 py-2 text-bubbles-sky-deep disabled:opacity-60"
                  >
                    <span className="font-display text-h4">{busy === p.id ? "Adding…" : p.label}</span>
                    <span className="text-body-sm font-bold">{formatMl(p.ml)}</span>
                  </button>
                ))}
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => { setCustomError(""); setOpen(true); }}
                  className="bubbles-press flex min-h-[64px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-bubbles-sky-deep bg-surface px-3 py-2 text-bubbles-sky-deep disabled:opacity-60"
                >
                  <span className="font-display text-h4">Custom</span>
                  <span className="text-body-sm font-bold">any amount</span>
                </button>
              </div>
              <LiveRegion message={message} />
              {message && <Notice tone="info">{message}</Notice>}
              {error && <ErrorNotice message={error} />}
            </Panel>
          </>
        )}
      </QueryView>

      <History
        title="Your drinks"
        status={history.status}
        error={history.error}
        onRetry={history.retry}
        entries={history.entries}
        freshId={history.freshId}
        signal="sky"
        renderEntry={(entry: Entry) => {
          const ml = toNumber(entry.volume);
          const kind = typeof entry.type === "string" && entry.type ? entry.type : "water";
          return (
            <EntryRow signal="sky" icon="hydration" title={ml === null ? "Drink" : `${formatMl(ml)} of ${beverageLabel(kind).toLowerCase()}`} />
          );
        }}
        empty={<EmptyState title="No drinks logged yet" text="Tap a glass or bottle above. Every sip adds to your garden." action={<LogButton signal="sky" onClick={() => setOpen(true)} wide>Add a drink</LogButton>} />}
      />
      <Disclaimer />

      <LogSheet open={open} onClose={() => setOpen(false)} signal="sky" icon="hydration" title="Add a drink" subtitle="Any amount" submitLabel="Save drink" onSubmit={submitCustom}>
        <Stepper
          id="drink-ml" label="Amount" value={customMl} onChange={(v) => { setCustomMl(v); setCustomError(""); }} error={customError || undefined}
          min={10} max={2000} step={50} unit="ml" fallback={250} presets={[100, 200, 330, 750]} signal="sky"
        />
        <Choices id="drink-type-sheet" legend="What are you drinking?" options={types} value={type} onChange={(v) => v && setType(v)} signal="sky" allowDeselect={false} hint={factorHint} />
      </LogSheet>
      <SavedToast trigger={savedAt} message="Drink added!" />
    </>
  );
}

function TodayPanel({ o }: { o: HydrationOverview }) {
  const goal = o.goal;
  if (goal.goal_ml === null) {
    // Fluid plan from a care team: no target, no percent, no remaining, no streak, no garden. Only what was logged.
    return (
      <Panel title="Today" kicker="Your fluid plan comes first">
        <Notice tone="info" title="A note from Bubbles" role="note">
          <p className="m-0">{goal.message}</p>
        </Notice>
        <p className="m-0 text-body text-ink">
          Logged today: <strong>{formatMl(o.raw_ml)}</strong>
        </p>
        <TypeSplit o={o} />
      </Panel>
    );
  }
  const garden = o.garden;
  const hint = reminderHint(o.reminders);
  return (
    <Panel title="Today" kicker="Bubbles' garden">
      <div className="flex flex-wrap items-center gap-6">
        {garden && <GardenScene level={garden.level} percent={o.percent ?? 0} />}
        <div className="min-w-[14rem] flex-1">
          <p className="m-0 font-display text-metric-lg text-default">{formatMl(o.effective_ml)}</p>
          <p className="m-0 text-body font-bold text-muted">of about {formatMl(goal.goal_ml)} today</p>
          <div
            role="progressbar" aria-label="Today's drinks progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={o.percent ?? 0}
            aria-valuetext={`${o.percent ?? 0} percent of today's target`}
            className="mt-3 h-3 overflow-hidden rounded-full bg-tint-sky"
          >
            <div className="h-full rounded-full bg-bubbles-sky-deep" style={{ width: `${o.percent ?? 0}%` }} />
          </div>
          <p className="m-0 mt-3 text-body text-ink">{o.message}</p>
          {o.remaining_ml !== null && o.remaining_ml > 0 && <p className="m-0 text-body-sm text-muted">About {formatMl(o.remaining_ml)} to go, whenever suits you.</p>}
        </div>
      </div>

      {garden && (
        <div className="rounded-2xl bg-blush px-4 py-3">
          <p className="m-0 font-extrabold text-ink">
            {garden.caption} <span className={`${PILL} ml-1 bg-tint-mint text-bubbles-mint-deep`}>{plural(garden.goal_days, "goal day")}</span>
          </p>
          <p className="m-0 mt-1 text-body-sm text-muted">
            {garden.next_level ? `${plural(garden.days_to_next, "more goal day")} until your garden reaches “${garden.next_level}”. ` : "Your garden is fully grown. "}
            {garden.total_litres} L watered in total. Your garden only ever grows.
          </p>
          {o.streak && (
            <p className="m-0 mt-1 text-body-sm text-muted">
              {o.streak.message}
              {o.streak.best > 1 && ` Your best run is ${plural(o.streak.best, "day")}.`}
            </p>
          )}
        </div>
      )}

      {hint && (
        <p className="m-0 text-body-sm font-bold text-ink-soft">
          {hint}{" "}
          <Link href="/settings" className="text-bubbles-grape-deep underline">
            Reminder settings
          </Link>
        </p>
      )}

      <details className="rounded-2xl bg-blush px-4 py-3 text-body-sm text-muted">
        <summary className="-my-[11px] cursor-pointer py-[11px] font-extrabold text-ink">How is this target worked out?</summary>
        <p className="m-0 mt-2">{goal.message}</p>
        <ul className="m-0 mt-2 list-disc pl-5">
          {goal.base_ml !== null && <li>Everyday base: {formatMl(goal.base_ml)}{goal.basis === "personal" ? " (from your weight)" : " (a general starting point)"}</li>}
          {goal.workout_bonus_ml > 0 && <li>Added for today&apos;s activity: {formatMl(goal.workout_bonus_ml)}</li>}
          <li>Different drinks count by how hydrating they are, so tea and coffee count a little less than water.</li>
        </ul>
        <p className="m-0 mt-2">It&apos;s a rough guide. Thirst, heat and how you feel matter too.</p>
      </details>

      <TypeSplit o={o} />
    </Panel>
  );
}

function TypeSplit({ o }: { o: HydrationOverview }) {
  const entries = Object.entries(o.by_type);
  if (entries.length === 0) return null;
  return (
    <ul className="m-0 flex list-none flex-wrap gap-2 p-0" aria-label="Today by drink">
      {entries.map(([kind, ml]) => (
        <li key={kind} className="rounded-full bg-blush px-3 py-1 text-body-sm font-bold text-ink-soft">
          {beverageLabel(kind)} {formatMl(ml)}
        </li>
      ))}
    </ul>
  );
}

