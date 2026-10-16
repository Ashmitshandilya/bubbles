"use client";

import { useState } from "react";
import { Skeleton } from "../../components/hub/HubKit";
import {
  Disclaimer, EmptyState, EntryNote, EntryRow, History, LogButton, LogSheet, SavedToast, TextArea, TextField, TrackerHero, TrackerShell,
} from "../../components/tracking/kit";
import { useTracker, present, timeLabel, type Entry } from "../../components/tracking/data";
import { Notice, QueryView } from "../../components/wellness/ui";
import { useWellnessQuery } from "../../components/wellness/useWellness";
import type { Adherence, Glp1Overview, MedsToday, Schedule, Warnings } from "../../app/lib/wellness-types";
import { DueList, WarningsPanel } from "./DueList";
import { Glp1Panel, LogbookPanel } from "./Glp1AndLogbook";
import { AdherencePanel, SavedLine, ScheduleList, ScheduleSheet, type SheetTarget } from "./Schedules";

export function MedicationsClient() {
  return (
    <TrackerShell title="Medications">
      <Medications />
    </TrackerShell>
  );
}

function Medications() {
  const [today, reloadToday] = useWellnessQuery<MedsToday>("/wellness/meds/today");
  const [schedules, reloadSchedules] = useWellnessQuery<{ schedules: Schedule[]; note: string } & Warnings>("/wellness/meds/schedules");
  const [adherence, reloadAdherence] = useWellnessQuery<Adherence>("/wellness/meds/adherence?days=30");
  const [glp1, reloadGlp1] = useWellnessQuery<Glp1Overview>("/wellness/meds/glp1");
  const list = useTracker("/health/medications", 30);
  const [target, setTarget] = useState<SheetTarget | null>(null);
  const [message, setMessage] = useState("");

  const reloadAll = () => {
    reloadToday();
    reloadSchedules();
    reloadAdherence();
    reloadGlp1();
  };
  const suggestions = [...new Set(list.entries.map((e) => String(e.name ?? "").trim()).filter(Boolean))];
  const add = (kind?: SheetTarget["kind"]) => setTarget({ kind });

  return (
    <>
      <TrackerHero
        signal="sky"
        icon="medications"
        kicker="MEDICINES & SUPPLEMENTS"
        title="Medications"
        why="Your medicine list helps Bubbles read symptom changes in context and gets you ready for doctor visits. Bubbles only records what you tell it; it never changes a dose."
        action={<LogButton signal="sky" onClick={() => add()}>Add a schedule</LogButton>}
      />
      <SavedLine message={message} />

      <QueryView query={today} onRetry={reloadToday} what="today's medicines" skeleton={<Skeleton className="h-56 rounded-3xl" />}>
        {(t) => (
          <>
            <DueList today={t} glp1={glp1.status === "ready" ? glp1.data : null} onChanged={reloadAll} onAdd={() => add()} />
            <WarningsPanel warnings={t} />
          </>
        )}
      </QueryView>

      <QueryView query={schedules} onRetry={reloadSchedules} what="your schedules" skeleton={<Skeleton className="h-40 rounded-3xl" />}>
        {(s) => (
          <ScheduleList
            schedules={s.schedules}
            onAdd={() => add()}
            onEdit={(sched) => setTarget({ schedule: sched })}
            onChanged={(m) => {
              if (m) setMessage(m);
              reloadAll();
            }}
          />
        )}
      </QueryView>

      {adherence.status === "ready" && <AdherencePanel data={adherence.data} />}

      {glp1.status === "ready" && glp1.data.detected && <Glp1Panel data={glp1.data} onChanged={reloadAll} onAddSchedule={() => add("glp1")} />}

      <LogbookPanel />

      <MedicineList list={list} />
      <Disclaimer />

      <ScheduleSheet
        target={target}
        suggestions={suggestions}
        onClose={() => setTarget(null)}
        onSaved={(m) => {
          setMessage(m);
          reloadAll();
        }}
      />
    </>
  );
}

/* ── The original medicine list (kept as it was: name, dose, reason, notes) ─────────────── */

function MedicineList({ list }: { list: ReturnType<typeof useTracker> }) {
  const { entries, status, error, retry, save, remove, freshId } = list;
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [dosage, setDosage] = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [nameError, setNameError] = useState("");

  async function submit(): Promise<string | null | false> {
    if (!name.trim()) {
      setNameError("Please add the name.");
      return false;
    }
    const body: Record<string, string> = { name: name.trim() };
    if (dosage.trim()) body.dosage = dosage.trim();
    if (reason.trim()) body.reason = reason.trim();
    if (notes.trim()) body.notes = notes.trim();
    const failure = await save(body);
    if (!failure) {
      setName("");
      setDosage("");
      setReason("");
      setNotes("");
    }
    return failure;
  }
  const openSheet = () => {
    setNameError("");
    setOpen(true);
  };

  return (
    <section aria-labelledby="medicine-list-title" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="medicine-list-title" className="m-0 font-display text-h2 text-default">
            Your medicine list
          </h2>
          <p className="m-0 text-body-sm text-muted">A simple list of what you take, for your own notes and doctor visits. Schedules above add times and reminders.</p>
        </div>
        <LogButton signal="sky" onClick={openSheet}>Add medication</LogButton>
      </div>
      <History
        onDelete={remove}
        title="On your list"
        status={status}
        error={error}
        onRetry={retry}
        entries={entries}
        freshId={freshId}
        signal="sky"
        renderEntry={(entry: Entry) => (
          <EntryRow signal="sky" icon="medications" title={present(entry.name) ? String(entry.name) : "Medication"} time={timeLabel(entry.date)}>
            {present(entry.dosage) && <EntryNote label="Dose" text={entry.dosage} />}
            {present(entry.reason) && <EntryNote label="For" text={entry.reason} />}
            <EntryNote text={entry.notes} />
          </EntryRow>
        )}
        empty={<EmptyState title="No medications added yet" text="Your medicine list helps Bubbles read symptom changes in context and gets you ready for doctor visits." action={<LogButton signal="sky" onClick={openSheet} wide>Add medication</LogButton>} />}
      />
      <LogSheet open={open} onClose={() => setOpen(false)} signal="sky" icon="medications" title="Add a medication" subtitle="For your list" submitLabel="Save medication" onSubmit={submit}>
        <TextField id="list-name" label="Name" value={name} onChange={(v) => { setName(v); setNameError(""); }} error={nameError || undefined} placeholder="Ibuprofen, iron, the pill…" maxLength={200} />
        <TextField id="list-dosage" label="Dose" value={dosage} onChange={setDosage} placeholder="200 mg twice a day" maxLength={100} optional />
        <TextField id="list-reason" label="What it's for" value={reason} onChange={setReason} placeholder="Period cramps" maxLength={300} optional />
        <TextArea id="list-notes" label="Notes" value={notes} onChange={setNotes} placeholder="Side effects, timing…" maxLength={2000} optional />
      </LogSheet>
      <SavedToast trigger={freshId} message="Saved to your list." />
      <Notice tone="calm">Medicines you add to the list and to schedules are separate records for now. Adding to a schedule doesn&apos;t change your list.</Notice>
    </section>
  );
}
