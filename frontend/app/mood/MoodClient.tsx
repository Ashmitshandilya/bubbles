"use client";

// The original mood form and history (unchanged behaviour), now with a pointer to the richer Mind page.

import { useState } from "react";
import Link from "next/link";
import {
  Choices, DetailChips, Disclaimer, EmptyState, EntryNote, EntryRow, History, LogButton, LogSheet, SavedToast, StatGrid, StatSkeleton,
  TextArea, TrackerHero, TrackerShell,
} from "../../components/tracking/kit";
import { computeStat, present, timeLabel, toNumber, useTracker, type Entry } from "../../components/tracking/data";

const MOODS = [
  { value: "2", label: "Awful" },
  { value: "4", label: "Low" },
  { value: "6", label: "Okay" },
  { value: "8", label: "Good" },
  { value: "10", label: "Great" },
];
const LEVELS = [
  { value: "0", label: "None" },
  { value: "3", label: "Mild" },
  { value: "5", label: "Some" },
  { value: "7", label: "High" },
  { value: "9", label: "Intense" },
];

const label = (options: { value: string; label: string }[], v: Entry["mood"]) => {
  const n = toNumber(v);
  return n === null ? null : (options.find((o) => Number(o.value) === n)?.label ?? `${n}/10`);
};

export function MoodClient() {
  return (
    <TrackerShell title="Mood">
      <Mood />
    </TrackerShell>
  );
}

function Mood() {
  const { entries, status, error, retry, save, remove, update, freshId } = useTracker("/health/mood", 30);
  const [open, setOpen] = useState(false);
  const [mood, setMood] = useState("");
  const [stress, setStress] = useState("");
  const [anxiety, setAnxiety] = useState("");
  const [notes, setNotes] = useState("");
  const [moodError, setMoodError] = useState("");

  async function submit(): Promise<string | null | false> {
    if (!mood) {
      setMoodError("Please add mood.");
      return false;
    }
    const body: Record<string, string | number> = { mood: Number(mood) };
    if (stress) body.stress = Number(stress);
    if (anxiety) body.anxiety = Number(anxiety);
    if (notes.trim()) body.notes = notes.trim();
    const failure = await save(body);
    if (!failure) {
      setMood("");
      setStress("");
      setAnxiety("");
      setNotes("");
    }
    return failure;
  }
  const openSheet = () => {
    setMoodError("");
    setOpen(true);
  };

  return (
    <>
      <TrackerHero
        signal="sun"
        icon="mood"
        kicker="EMOTIONAL WELLBEING"
        title="Mood"
        why="A quick check-in helps Bubbles see how mood moves with your cycle, sleep and activity."
        action={<LogButton signal="sun" onClick={openSheet}>Check in</LogButton>}
      />
      <p className="m-0 rounded-2xl bg-tint-sun px-4 py-3 text-body-sm font-bold text-ink">
        Want one-tap check-ins, a year in pixels, a private journal and calm breathing tools?{" "}
        <Link href="/mind" className="text-bubbles-grape-deep underline">
          Open Mind
        </Link>
        .
      </p>
      {status === "loading" && entries.length === 0 && <StatSkeleton count={3} />}
      {status === "ready" && entries.length > 0 && (
        <StatGrid
          signal="sun"
          stats={[
            computeStat({ label: "Latest mood", kind: "latest", field: "mood", unit: "/10", decimals: 0 }, entries),
            computeStat({ label: "7-day average", kind: "avg", field: "mood", days: 7, unit: "/10" }, entries),
            computeStat({ label: "Check-ins", kind: "count", note: "last 30 days" }, entries),
          ]}
        />
      )}
      <History
        onDelete={remove}
        onEdit={update}
        status={status}
        error={error}
        onRetry={retry}
        entries={entries}
        freshId={freshId}
        signal="sun"
        renderEntry={(entry) => {
          const chips = [
            present(entry.stress) && { label: "Stress", value: label(LEVELS, entry.stress) ?? String(entry.stress) },
            present(entry.anxiety) && { label: "Anxiety", value: label(LEVELS, entry.anxiety) ?? String(entry.anxiety) },
          ].filter(Boolean) as { label: string; value: string }[];
          return (
            <EntryRow signal="sun" icon="mood" title={label(MOODS, entry.mood) ?? "Check-in"} time={timeLabel(entry.date)}>
              <DetailChips items={chips} />
              <EntryNote text={entry.notes} />
            </EntryRow>
          );
        }}
        empty={<EmptyState title="No check-ins yet" text="A quick check-in helps Bubbles see how mood moves with your cycle, sleep and activity." action={<LogButton signal="sun" onClick={openSheet} wide>Check in</LogButton>} />}
      />
      <Disclaimer />
      <LogSheet open={open} onClose={() => setOpen(false)} signal="sun" icon="mood" title="How are you feeling?" subtitle={new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" })} submitLabel="Save check-in" onSubmit={submit}>
        <Choices id="mood-value" legend="Mood" options={MOODS} value={mood} onChange={(v) => { setMood(v); setMoodError(""); }} columns={5} signal="sun" error={moodError || undefined} />
        <Choices id="mood-stress" legend="Stress" options={LEVELS} value={stress} onChange={setStress} columns={5} signal="sun" optional />
        <Choices id="mood-anxiety" legend="Anxiety" options={LEVELS} value={anxiety} onChange={setAnxiety} columns={5} signal="sun" optional />
        <TextArea id="mood-notes" label="What's on your mind?" value={notes} onChange={setNotes} placeholder="What shaped your mood today…" maxLength={2000} optional />
      </LogSheet>
      <SavedToast trigger={freshId} message="Saved! Bubbles will use this to learn your baseline." />
    </>
  );
}
