"use client";

import { useState } from "react";
import {
  Choices, DateField, DetailChips, Disclaimer, EmptyState, EntryNote, EntryRow, Fold, History, LogButton, LogSheet, SavedToast, StatGrid,
  StatSkeleton, Stepper, TextArea, TrackerHero, TrackerShell, WeekBars,
} from "../../components/tracking/kit";
import { computeStat, formatNumber, todayISO, toNumber, useTracker, type Entry } from "../../components/tracking/data";
import { QueryView, SafetyCard, ToggleChips, TimeField } from "../../components/wellness/ui";
import { useWellnessQuery, useWellnessSend } from "../../components/wellness/useWellness";
import { isSafety, type SafetyResponse, type SleepOverview } from "../../app/lib/wellness-types";
import { humanizeKey } from "../../app/lib/wellness-format";
import { GoalEditor, InsightsPanel, RhythmPanel, ScorePanel, WeekdayPanel, WinddownPanel } from "./SleepPanels";
import { Skeleton } from "../../components/hub/HubKit";

const RESTED = [
  { value: "2", label: "Drained" },
  { value: "4", label: "Tired" },
  { value: "6", label: "Okay" },
  { value: "8", label: "Good" },
  { value: "10", label: "Great" },
];

const TAG_LABELS: Record<string, string> = {
  caffeine: "Caffeine",
  alcohol: "Alcohol",
  stress: "A stressful day",
  late_meal: "A late meal",
  screen: "Late screen time",
  exercise: "Exercise that day",
};
const DEFAULT_TAGS = ["caffeine", "alcohol", "stress", "late_meal", "screen", "exercise"];

function restedLabel(v: Entry["quality"]): string | null {
  const n = toNumber(v);
  if (n === null) return null;
  return RESTED.find((r) => Number(r.value) === n)?.label ?? `${n}/10`;
}

export function SleepClient() {
  return (
    <TrackerShell title="Sleep">
      <Sleep />
    </TrackerShell>
  );
}

function Sleep() {
  const { entries, status, error, retry, remove, freshId } = useTracker("/health/sleep", 30);
  const [overview, reloadOverview] = useWellnessQuery<SleepOverview>("/wellness/sleep/overview?days=30");
  const send = useWellnessSend();

  const [open, setOpen] = useState(false);
  const [hours, setHours] = useState("");
  const [bedtime, setBedtime] = useState("");
  const [wake, setWake] = useState("");
  const [nap, setNap] = useState("");
  const [quality, setQuality] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [date, setDate] = useState(() => todayISO());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [safety, setSafety] = useState<SafetyResponse | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const tagOptions = (overview.status === "ready" ? overview.data.tags : DEFAULT_TAGS).map((t) => ({ value: t, label: TAG_LABELS[t] ?? humanizeKey(t) }));

  function openSheet() {
    setErrors({});
    setDate(todayISO());
    setOpen(true);
  }

  async function submit(): Promise<string | null | false> {
    const next: Record<string, string> = {};
    const h = Number(hours);
    const hasHours = hours.trim() !== "";
    if (hasHours && (!Number.isFinite(h) || h < 0.25 || h > 24)) next.hours = "Hours slept must be between 0.25 and 24.";
    if ((bedtime && !wake) || (!bedtime && wake)) next.times = "Add both a bedtime and a wake time, or neither.";
    const napMinutes = nap.trim() === "" ? null : Number(nap);
    if (napMinutes !== null && (!Number.isFinite(napMinutes) || napMinutes < 0 || napMinutes > 300)) next.nap = "A nap can be 0 to 300 minutes.";
    if (!hasHours && !(bedtime && wake) && !(napMinutes && napMinutes > 0)) next.hours = "Add how long you slept, or a bedtime and wake time, or a nap.";
    setErrors(next);
    if (Object.keys(next).length) return false;

    const body: Record<string, unknown> = { date };
    if (hasHours) body.duration = h;
    if (bedtime && wake) {
      body.bedtime = bedtime;
      body.wake = wake;
    }
    if (napMinutes) body.nap_minutes = napMinutes;
    if (quality) body.quality = Number(quality);
    if (tags.length) body.tags = tags;
    if (notes.trim()) body.notes = notes.trim();

    const result = await send<{ status: string } | SafetyResponse>("/wellness/sleep/log", "POST", body);
    if (!result.ok) return `${result.message} Your entry is still here, so you can try again.`;
    if (isSafety(result.data)) {
      setSafety(result.data); // urgent wording: nothing was saved; keep what was typed and show the message first
      return null;
    }
    setSafety(null);
    setHours("");
    setBedtime("");
    setWake("");
    setNap("");
    setQuality("");
    setTags([]);
    setNotes("");
    setSavedAt(`${Date.now()}`);
    retry();
    reloadOverview();
    return null;
  }

  const log = <LogButton signal="grape" onClick={openSheet}>Log sleep</LogButton>;

  return (
    <>
      <TrackerHero
        signal="grape"
        icon="sleep"
        kicker="REST & RECOVERY"
        title="Sleep"
        why="Your nights shape mood, energy and cravings. Logging sleep lets Bubbles see how they connect across your cycle."
        action={log}
      />

      {safety && <SafetyCard response={safety} onClose={() => setSafety(null)} />}

      <QueryView
        query={overview}
        onRetry={reloadOverview}
        what="your sleep insights"
        skeleton={
          <div className="flex flex-col gap-6">
            <Skeleton className="h-64 rounded-3xl" />
            <Skeleton className="h-48 rounded-3xl" />
          </div>
        }
      >
        {(data) => (
          <>
            <ScorePanel overview={data} />
            <Fold title="Rhythm and patterns">
              <RhythmPanel overview={data} />
              <WeekdayPanel overview={data} />
              <InsightsPanel overview={data} />
            </Fold>
            <Fold title="Goal and wind-down">
              <GoalEditor key={`${data.goal.hours}|${data.goal.bedtime ?? ""}|${data.goal.wake_time ?? ""}`} goal={data.goal} onSaved={reloadOverview} />
              <WinddownPanel overview={data} />
            </Fold>
            <p className="m-0 text-chip font-semibold text-muted">{data.disclaimer}</p>
          </>
        )}
      </QueryView>

      {overview.status === "error" && status === "ready" && entries.length > 0 && (
        <StatGrid
          signal="grape"
          stats={[
            computeStat({ label: "Last night", kind: "latest", field: "duration", unit: "h" }, entries),
            computeStat({ label: "7-night average", kind: "avg", field: "duration", days: 7, unit: "h", note: "last 7 days" }, entries),
            computeStat({ label: "How rested", kind: "avg", field: "quality", days: 7, unit: "/10", note: "average, last 7 days" }, entries),
            computeStat({ label: "Nights logged", kind: "count", note: "last 30 days" }, entries),
          ]}
        />
      )}
      {status === "loading" && entries.length === 0 && overview.status === "error" && <StatSkeleton count={4} />}
      {status === "ready" && entries.length > 0 && <WeekBars title="Hours slept this week" entries={entries} field="duration" unit="h" signal="grape" minScale={9} />}

      <History
        onDelete={remove}
        status={status}
        error={error}
        onRetry={retry}
        entries={entries}
        freshId={freshId}
        signal="grape"
        renderEntry={(entry) => {
          const hoursSlept = toNumber(entry.duration);
          const rested = restedLabel(entry.quality);
          return (
            <EntryRow signal="grape" icon="sleep" title={hoursSlept === null ? "Sleep" : `${formatNumber(hoursSlept, "h", 2)} of sleep`}>
              <DetailChips items={rested ? [{ label: "Felt", value: rested }] : []} />
              <EntryNote text={entry.notes} />
            </EntryRow>
          );
        }}
        empty={
          <EmptyState
            title="No nights logged yet"
            text="Log last night's sleep and Bubbles will start learning your usual rhythm."
            action={<LogButton signal="grape" onClick={openSheet} wide>Log last night</LogButton>}
          />
        }
      />
      <Disclaimer />

      <LogSheet
        open={open}
        onClose={() => setOpen(false)}
        signal="grape"
        icon="sleep"
        title="How did you sleep?"
        subtitle={new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" })}
        submitLabel="Save sleep"
        onSubmit={submit}
      >
        <Stepper
          id="sleep-hours"
          label="Hours slept"
          value={hours}
          onChange={(v) => {
            setHours(v);
            setErrors((e) => ({ ...e, hours: "" }));
          }}
          error={errors.hours || undefined}
          hint="Or leave this empty and add a bedtime and wake time below: Bubbles works out the hours."
          min={0}
          max={24}
          step={0.5}
          unit="h"
          fallback={7.5}
          signal="grape"
          optional
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TimeField id="sleep-bed" label="Bedtime" value={bedtime} onChange={setBedtime} optional error={errors.times || undefined} />
          <TimeField id="sleep-wake" label="Wake time" value={wake} onChange={setWake} optional />
        </div>
        <Choices id="sleep-quality" legend="How rested do you feel?" options={RESTED} value={quality} onChange={setQuality} columns={5} signal="grape" optional />
        <ToggleChips
          legend="Anything that might have affected the night?"
          options={tagOptions}
          selected={tags}
          onToggle={(t) => setTags((cur) => (cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]))}
          signal="grape"
          hint="Tags are optional. After a few nights Bubbles can look for patterns, always as tendencies, never causes."
          optional
        />
        <Stepper id="sleep-nap" label="Nap" value={nap} onChange={setNap} error={errors.nap || undefined} min={0} max={300} step={15} unit="min" fallback={20} signal="grape" optional hint="Naps are kept separate from your night." />
        <DateField id="sleep-date" label="Which morning?" value={date} onChange={setDate} max={todayISO()} hint="The day you woke up. Leave as today for last night." />
        <TextArea id="sleep-notes" label="Anything Bubbles should know?" value={notes} onChange={setNotes} placeholder="Woke up twice, late coffee…" maxLength={1000} optional />
      </LogSheet>
      <SavedToast trigger={savedAt} message="Sleep saved. Sweet dreams logged!" />
    </>
  );
}
