"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Choices, DetailChips, Disclaimer, EmptyState, EntryNote, EntryRow, History, LogButton, LogSheet, SavedToast,
  StatGrid, StatSkeleton, Stepper, TextArea, TextField, TrackerHero, TrackerShell, WeekBars,
} from "../../components/tracking/kit";
import { computeStat, formatNumber, toNumber, useTracker } from "../../components/tracking/data";

const ACTIVITY_TYPES = ["Walk", "Run", "Yoga", "Strength", "Cycle", "Swim", "Dance", "HIIT", "Stretch", "Sports"];

const INTENSITY = [
  { value: "light", label: "Light" },
  { value: "moderate", label: "Moderate" },
  { value: "intense", label: "Intense" },
];

export function ActivityClient() {
  return (
    <TrackerShell title="Activity">
      <Activity />
    </TrackerShell>
  );
}

function Activity() {
  const { entries, status, error, retry, save, freshId } = useTracker("/health/activity", 30);
  const [open, setOpen] = useState(false);
  const [type, setType] = useState("Walk");
  const [minutes, setMinutes] = useState("30");
  const [intensity, setIntensity] = useState("moderate");
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState<{ type?: string; minutes?: string }>({});

  const openSheet = () => {
    setErrors({});
    setOpen(true);
  };

  async function submit(): Promise<string | null | false> {
    const n = Number(minutes);
    const next: { type?: string; minutes?: string } = {};
    if (!type.trim()) next.type = "Please add what you did.";
    if (minutes.trim() === "" || !Number.isFinite(n) || n < 0 || n > 1440) next.minutes = "Minutes must be between 0 and 1440.";
    setErrors(next);
    if (next.type || next.minutes) return false;
    const body: Record<string, string | number> = { type: type.trim(), duration: n };
    if (intensity) body.intensity = intensity;
    if (notes.trim()) body.notes = notes.trim();
    const failure = await save(body);
    if (!failure) setNotes("");
    return failure;
  }

  const log = <LogButton signal="peach" onClick={openSheet}>Log activity</LogButton>;
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });

  return (
    <>
      <TrackerHero
        signal="peach"
        icon="activity"
        kicker="MOVEMENT"
        title="Activity"
        why="Movement affects your sleep, mood and recovery differently through your cycle. Logs help Bubbles learn what works for you."
        action={log}
      />
      {status === "loading" && entries.length === 0 && <StatSkeleton count={4} />}
      {status === "ready" && entries.length > 0 && (
        <>
          <StatGrid
            signal="peach"
            stats={[
              computeStat({ label: "This week", kind: "sum", field: "duration", days: 7, unit: "min", decimals: 0, note: "minutes, last 7 days" }, entries),
              computeStat({ label: "Sessions", kind: "count", days: 7, note: "last 7 days" }, entries),
              computeStat({ label: "Average session", kind: "avg", field: "duration", unit: "min", decimals: 0, note: "last 30 days" }, entries),
              computeStat({ label: "Total", kind: "sum", field: "duration", unit: "min", decimals: 0, note: "last 30 days" }, entries),
            ]}
          />
          <WeekBars title="Active minutes this week" entries={entries} field="duration" unit="min" signal="peach" minScale={30} decimals={0} />
        </>
      )}
      <History
        status={status}
        error={error}
        onRetry={retry}
        entries={entries}
        freshId={freshId}
        signal="peach"
        renderEntry={(entry) => {
          const mins = toNumber(entry.duration);
          const level = INTENSITY.find((i) => i.value === entry.intensity)?.label ?? (entry.intensity ? String(entry.intensity) : null);
          return (
            <EntryRow signal="peach" icon="activity" title={String(entry.type ?? "Activity")}>
              <DetailChips
                items={[
                  ...(mins === null ? [] : [{ label: "Time", value: formatNumber(mins, "min", 0) }]),
                  ...(level ? [{ label: "Intensity", value: level }] : []),
                ]}
              />
              <EntryNote text={entry.notes} />
            </EntryRow>
          );
        }}
        empty={
          <EmptyState
            title="No activity logged yet"
            text="A walk counts! Log any movement and Bubbles will start learning your rhythm."
            action={<LogButton signal="peach" onClick={openSheet} wide>Log your first activity</LogButton>}
          />
        }
      />
      <Link
        href="/companion"
        className="bubbles-press inline-flex min-h-[48px] items-center justify-center self-start rounded-full bg-bubbles-grape px-5 text-body-sm font-extrabold text-white no-underline shadow-[0_5px_0_var(--bubbles-grape-deep)]"
      >
        Ask Bubbles what movement suits this week
      </Link>
      <Disclaimer />
      <LogSheet open={open} onClose={() => setOpen(false)} signal="peach" icon="activity" title="How did you move?" subtitle={today} submitLabel="Save activity" onSubmit={submit}>
        <TextField
          id="activity-type"
          label="Activity"
          value={type}
          onChange={(v) => {
            setType(v);
            setErrors((e) => ({ ...e, type: undefined }));
          }}
          placeholder="Type it or pick one below"
          maxLength={100}
          suggestions={ACTIVITY_TYPES}
          signal="peach"
          error={errors.type}
        />
        <Stepper
          id="activity-minutes"
          label="Minutes"
          value={minutes}
          onChange={(v) => {
            setMinutes(v);
            setErrors((e) => ({ ...e, minutes: undefined }));
          }}
          min={0}
          max={1440}
          step={5}
          unit="min"
          fallback={30}
          presets={[15, 30, 45, 60]}
          signal="peach"
          error={errors.minutes}
        />
        <Choices id="activity-intensity" legend="Intensity" options={INTENSITY} value={intensity} onChange={setIntensity} columns={3} signal="peach" optional />
        <TextArea id="activity-notes" label="Notes" value={notes} onChange={setNotes} placeholder="How you felt, where you went…" maxLength={2000} optional />
      </LogSheet>
      <SavedToast trigger={freshId} message="Nice moving! Activity saved." />
    </>
  );
}
