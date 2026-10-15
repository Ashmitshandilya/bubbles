"use client";

import { useState } from "react";
import {
  Choices, DetailChips, Disclaimer, EmptyState, EntryNote, EntryRow, History, LogButton, LogSheet, SavedToast, StatGrid,
  StatSkeleton, TextArea, TextField, TrackerHero, TrackerShell,
} from "../../components/tracking/kit";
import { computeStat, daysAgo, toNumber, useTracker, type Entry } from "../../components/tracking/data";

const COMMON_SYMPTOMS = ["Cramps", "Headache", "Fatigue", "Bloating", "Back pain", "Breast tenderness", "Acne", "Nausea", "Mood swings", "Brain fog"];

const SEVERITY = Array.from({ length: 10 }, (_, i) => ({ value: String(i + 1), label: String(i + 1) }));

/** Most frequent symptoms in the last 30 days, grouped case-insensitively. */
function topSymptoms(entries: Entry[]): { name: string; count: number }[] {
  const counts = new Map<string, { name: string; count: number }>();
  for (const e of entries) {
    if (typeof e.symptom !== "string" || daysAgo(e.date) > 29) continue;
    const key = e.symptom.trim().toLowerCase();
    const hit = counts.get(key) ?? { name: e.symptom.trim(), count: 0 };
    hit.count += 1;
    counts.set(key, hit);
  }
  return [...counts.values()].sort((a, b) => b.count - a.count).slice(0, 6);
}

export function SymptomsClient() {
  return (
    <TrackerShell title="Symptoms">
      <Symptoms />
    </TrackerShell>
  );
}

function Symptoms() {
  const { entries, status, error, retry, save, freshId } = useTracker("/health/symptoms", 30);
  const [open, setOpen] = useState(false);
  const [symptom, setSymptom] = useState("");
  const [severity, setSeverity] = useState("");
  const [notes, setNotes] = useState("");
  const [symptomError, setSymptomError] = useState("");

  const openSheet = (prefill?: string) => {
    if (prefill) setSymptom(prefill);
    setSymptomError("");
    setOpen(true);
  };

  async function submit(): Promise<string | null | false> {
    const name = symptom.trim();
    if (!name) {
      setSymptomError("Please add the symptom you noticed.");
      return false;
    }
    const body: Record<string, string | number> = { symptom: name };
    if (severity) body.severity = Number(severity);
    if (notes.trim()) body.notes = notes.trim();
    const failure = await save(body);
    if (!failure) {
      setSymptom("");
      setSeverity("");
      setNotes("");
    }
    return failure;
  }

  const top = topSymptoms(entries);
  const log = <LogButton signal="pink" onClick={() => openSheet()}>Log symptom</LogButton>;
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });

  return (
    <>
      <TrackerHero
        signal="pink"
        icon="symptoms"
        kicker="HOW YOU FEEL"
        title="Symptoms"
        why="Symptoms often cluster around your period, poor sleep or stress. Logging them lets Bubbles find your patterns."
        action={log}
      />
      {status === "loading" && entries.length === 0 && <StatSkeleton count={3} />}
      {status === "ready" && entries.length > 0 && (
        <>
          <StatGrid
            signal="pink"
            stats={[
              computeStat({ label: "This week", kind: "count", days: 7, note: "symptoms logged" }, entries),
              computeStat({ label: "Average severity", kind: "avg", field: "severity", days: 30, unit: "/10", note: "last 30 days" }, entries),
              computeStat({ label: "Logged", kind: "count", note: "last 30 days" }, entries),
            ]}
          />
          {top.length > 0 && (
            <section aria-labelledby="symptom-frequency" className="rounded-[28px] border-2 border-line bg-surface p-5">
              <h2 id="symptom-frequency" className="m-0 font-display text-h3 text-default">Most frequent</h2>
              <p className="m-0 mt-1 text-body-sm font-semibold text-muted">Last 30 days · tap one to log it again</p>
              <ul className="bubbles-stagger m-0 mt-3 flex list-none flex-wrap gap-2 p-0">
                {top.map(({ name, count }) => (
                  <li key={name}>
                    <button
                      type="button"
                      onClick={() => openSheet(name)}
                      aria-label={`Log ${name} again (logged ${count} ${count === 1 ? "time" : "times"} in 30 days)`}
                      className="bubbles-press inline-flex min-h-[44px] items-center gap-2 rounded-full border-2 border-line bg-tint-pink px-4 text-body-sm font-extrabold text-bubbles-pink-deep"
                    >
                      {name}
                      <span className="rounded-full bg-surface px-2 py-0.5 text-chip">×{count}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      <History
        status={status}
        error={error}
        onRetry={retry}
        entries={entries}
        freshId={freshId}
        signal="pink"
        renderEntry={(entry) => {
          const level = toNumber(entry.severity);
          return (
            <EntryRow signal="pink" icon="symptoms" title={String(entry.symptom ?? "Symptom")}>
              <DetailChips items={level === null ? [] : [{ label: "Severity", value: `${level}/10` }]} />
              <EntryNote text={entry.notes} />
            </EntryRow>
          );
        }}
        empty={
          <EmptyState
            title="No symptoms logged yet"
            text="When something feels off, log it here. Over time Bubbles can spot what tends to come with it."
            action={<LogButton signal="pink" onClick={() => openSheet()} wide>Log a symptom</LogButton>}
          />
        }
      />
      <p className="m-0 rounded-2xl bg-tint-sun px-4 py-3 text-body-sm font-bold text-bubbles-sun-deep">
        If a symptom is severe, sudden or worrying, please contact a clinician or your local emergency number. Don&apos;t wait for a pattern.
      </p>
      <Disclaimer />
      <LogSheet open={open} onClose={() => setOpen(false)} signal="pink" icon="symptoms" title="What are you feeling?" subtitle={today} submitLabel="Save symptom" onSubmit={submit}>
        <TextField
          id="symptom-name"
          label="Symptom"
          value={symptom}
          onChange={(v) => {
            setSymptom(v);
            setSymptomError("");
          }}
          placeholder="Type it or pick one below"
          maxLength={200}
          suggestions={COMMON_SYMPTOMS}
          signal="pink"
          error={symptomError || undefined}
        />
        <Choices
          id="symptom-severity"
          legend="How strong is it?"
          hint="1 = barely there · 10 = the worst you can imagine"
          options={SEVERITY}
          value={severity}
          onChange={setSeverity}
          columns={5}
          signal="pink"
          optional
        />
        <TextArea id="symptom-notes" label="Notes" value={notes} onChange={setNotes} placeholder="When it started, what helps…" maxLength={2000} optional />
      </LogSheet>
      <SavedToast trigger={freshId} message="Symptom saved. Bubbles will look for patterns." />
    </>
  );
}
