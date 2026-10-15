"use client";

// GLP-1 tracker (dose day, injection-site rotation, appetite / nausea log, protein and fluid nudges) and the doctor logbook.
// The UI never suggests a dose change: the prescriber decides, and every worrying note points to the prescriber or pharmacist.

import { useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY } from "../../components/hub/HubKit";
import { Choices, Stepper, TextArea } from "../../components/tracking/kit";
import { BTN_TEXT, EmptyNote, ErrorNotice, LiveRegion, Notice, Panel, QueryView, SafetyCard, SelectField } from "../../components/wellness/ui";
import { useWellnessQuery, useWellnessSend } from "../../components/wellness/useWellness";
import { appetiteWords, SITE_LABELS, SKIP_REASON_LABELS } from "../../app/lib/wellness-meds";
import { plural, shortDay } from "../../app/lib/wellness-format";
import { isSafety, type Glp1Overview, type Logbook, type SafetyResponse } from "../../app/lib/wellness-types";

const APPETITE = [1, 2, 3, 4, 5].map((n) => ({ value: String(n), label: appetiteWords(n) }));

export function Glp1Panel({ data, onChanged, onAddSchedule }: { data: Glp1Overview; onChanged: () => void; onAddSchedule: () => void }) {
  const send = useWellnessSend();
  const [appetite, setAppetite] = useState("");
  const [nausea, setNausea] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [said, setSaid] = useState("");
  const [safety, setSafety] = useState<SafetyResponse | null>(null);
  const [nudges, setNudges] = useState<string[] | null>(null);
  const sched = data.schedule;

  async function save() {
    if (!appetite && nausea.trim() === "") {
      setError("Add how your appetite is, or how nauseous you feel, then save.");
      return;
    }
    setBusy(true);
    setError("");
    const body: Record<string, unknown> = {};
    if (appetite) body.appetite = Number(appetite);
    if (nausea.trim() !== "") body.nausea = Number(nausea);
    if (notes.trim()) body.notes = notes.trim();
    const result = await send<{ nudges?: string[] } | SafetyResponse>("/wellness/meds/glp1/log", "POST", body);
    setBusy(false);
    if (!result.ok) return setError(`${result.message} Your entry is still here.`);
    if (isSafety(result.data)) return setSafety(result.data);
    setSafety(null);
    setAppetite("");
    setNausea("");
    setNotes("");
    setNudges((result.data as { nudges?: string[] }).nudges ?? null);
    setSaid("Saved. Thank you for logging how you feel.");
    onChanged();
  }

  const shownNudges = nudges ?? data.nudges;
  return (
    <Panel title="Weekly injection tracker" kicker="Dose day, spots and how you feel">
      {safety && <SafetyCard response={safety} onClose={() => setSafety(null)} />}
      <Notice tone="info">{data.note}</Notice>

      {sched ? (
        <div className="rounded-2xl bg-blush px-4 py-3">
          <p className="m-0 font-display text-h4 text-default">
            {sched.name}
            {sched.dose_label ? ` · ${sched.dose_label}` : ""}
          </p>
          <p className="m-0 mt-1 text-body text-ink">
            {sched.reminder ??
              (sched.next_dose_date
                ? `Your next dose day is ${shortDay(sched.next_dose_date, true)}${sched.days_until != null ? ` (in ${plural(sched.days_until, "day")})` : ""}.`
                : "No upcoming dose day found in the next week.")}
          </p>
          <p className="m-0 mt-2 text-body-sm text-ink-soft">
            Next spot to consider: <strong>{sched.suggested_site_label}</strong>
            {sched.last_site ? ` (you last noted: ${SITE_LABELS[sched.last_site] ?? sched.last_site.replaceAll("_", " ")})` : ""}. {sched.site_note}
          </p>
          <p className="m-0 mt-1 text-body-sm text-muted">Mark the dose as taken in today&apos;s list above, and Bubbles will ask which spot you used.</p>
        </div>
      ) : (
        <EmptyNote title="Add your weekly injection" action={<button type="button" onClick={onAddSchedule} className={BTN_PRIMARY}>Add weekly injection</button>}>
          Add the medicine, its day and time as your prescriber gave them. Bubbles will count down to dose day and remember your last spot.
        </EmptyNote>
      )}

      <div className="flex flex-col gap-4">
        <h3 className="m-0 font-display text-h4 text-default">How are you feeling?</h3>
        <Choices id="glp1-appetite" legend="Appetite" options={APPETITE} value={appetite} onChange={setAppetite} signal="sky" columns={5} optional />
        <Stepper id="glp1-nausea" label="Nausea (0 is none, 10 is the worst)" value={nausea} onChange={setNausea} min={0} max={10} step={1} fallback={0} signal="sky" optional />
        <TextArea id="glp1-notes" label="Anything else?" value={notes} onChange={setNotes} maxLength={500} placeholder="Optional" optional />
        {error && <ErrorNotice message={error} />}
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" disabled={busy} onClick={() => void save()} className={BTN_PRIMARY}>
            {busy ? "Saving…" : "Save how I feel"}
          </button>
        </div>
        <LiveRegion message={said} />
        {said && <p className="m-0 text-body-sm font-extrabold text-bubbles-mint-deep">{said}</p>}
      </div>

      <ul className="m-0 flex list-none flex-col gap-2 p-0" aria-label="Gentle notes">
        {shownNudges.map((n) => (
          <li key={n} className="rounded-2xl bg-tint-sky px-4 py-2 text-body-sm text-ink">
            {n}
          </li>
        ))}
      </ul>

      {data.recent_logs.length > 0 && (
        <details className="rounded-2xl bg-blush px-4 py-3 text-body-sm text-muted">
          <summary className="-my-[11px] cursor-pointer py-[11px] font-extrabold text-ink">Recent entries</summary>
          <ul className="m-0 mt-2 list-none space-y-1 p-0">
            {data.recent_logs.slice(0, 7).map((l) => (
              <li key={l.date}>
                <strong className="text-ink">{shortDay(l.date, true)}</strong>
                {l.appetite != null && ` · appetite ${appetiteWords(l.appetite).toLowerCase()}`}
                {l.nausea != null && ` · nausea ${l.nausea}/10`}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Panel>
  );
}

/* ── Doctor logbook ─────────────────────────────────────────────────── */

const PRINT_CSS = `
@media print {
  body * { visibility: hidden !important; }
  .bubbles-logbook, .bubbles-logbook * { visibility: visible !important; }
  .bubbles-logbook { position: absolute; left: 0; top: 0; width: 100%; border: 0 !important; padding: 0 !important; background: #fff !important; color: #000 !important; }
  .bubbles-no-print { display: none !important; }
  .bubbles-logbook table { border-collapse: collapse; width: 100%; }
  .bubbles-logbook th, .bubbles-logbook td { border: 1px solid #999; padding: 4px 6px; text-align: left; font-size: 11pt; }
}
`;

export function LogbookPanel() {
  const [open, setOpen] = useState(false);
  const [days, setDays] = useState("30");
  return (
    <Panel title="Doctor logbook" kicker="A printable summary">
      <p className="m-0 text-body-sm text-muted">A one-page record of what you took, skipped and didn&apos;t record, ready to bring to an appointment. Print it or save it as a PDF from your browser&apos;s print window.</p>
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-44">
          <SelectField id="logbook-days" label="Covers" value={days} onChange={setDays} options={[{ value: "14", label: "Last 14 days" }, { value: "30", label: "Last 30 days" }, { value: "90", label: "Last 90 days" }]} />
        </div>
        <button type="button" aria-expanded={open} onClick={() => setOpen((v) => !v)} className={BTN_SECONDARY}>
          {open ? "Hide logbook" : "Open logbook"}
        </button>
      </div>
      {open && <LogbookView key={days} days={days} />}
    </Panel>
  );
}

function LogbookView({ days }: { days: string }) {
  const [logbook, reload] = useWellnessQuery<Logbook>(`/wellness/meds/logbook?days=${days}`);
  return (
    <QueryView query={logbook} onRetry={reload} what="the logbook">
      {(b) => (
        <div>
          <style>{PRINT_CSS}</style>
          <div className="bubbles-no-print mb-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => window.print()} className={BTN_PRIMARY}>
              Print or save as PDF
            </button>
          </div>
          <article className="bubbles-logbook rounded-2xl border border-line bg-surface p-4 text-ink" aria-label="Medication logbook">
            <h3 className="m-0 font-display text-h3">Medication logbook</h3>
            <p className="m-0 text-body-sm text-muted">
              Last {b.window_days} days · generated {shortDay(b.generated_on)} by Bubbles
            </p>
            {b.medications.length === 0 ? (
              <p className="mt-3 text-body-sm">No medicines have been added yet.</p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-left text-body-sm">
                  <caption className="sr-only">What was taken, skipped and not recorded for each medicine</caption>
                  <thead>
                    <tr className="border-b-2 border-line">
                      <th scope="col" className="py-2 pr-3">Medicine</th>
                      <th scope="col" className="py-2 pr-3">Schedule</th>
                      <th scope="col" className="py-2 pr-3">Taken</th>
                      <th scope="col" className="py-2 pr-3">Skipped</th>
                      <th scope="col" className="py-2 pr-3">No record</th>
                      <th scope="col" className="py-2">Last taken</th>
                    </tr>
                  </thead>
                  <tbody>
                    {b.medications.map((m) => (
                      <tr key={`${m.name}-${m.schedule}`} className="border-b border-line align-top">
                        <th scope="row" className="py-2 pr-3 font-bold">
                          {m.name}
                          {m.dose_label ? ` ${m.dose_label}` : ""}
                          {!m.active && <span className="font-semibold text-muted"> (paused)</span>}
                        </th>
                        <td className="py-2 pr-3">{m.schedule}</td>
                        <td className="py-2 pr-3">{m.taken}{m.percent !== null && ` (${m.percent}%)`}</td>
                        <td className="py-2 pr-3">
                          {m.skipped}
                          {Object.keys(m.skip_reasons).length > 0 && (
                            <span className="block text-muted">{Object.entries(m.skip_reasons).map(([r, n]) => `${(SKIP_REASON_LABELS[r] ?? r).toLowerCase()} ×${n}`).join(", ")}</span>
                          )}
                        </td>
                        <td className="py-2 pr-3">{m.not_recorded}</td>
                        <td className="py-2">{m.last_taken ? shortDay(m.last_taken) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="mt-3 text-body-sm">
              <strong>Allergies:</strong> {b.allergies.length ? b.allergies.join(", ") : "none recorded"}
            </p>
            {b.interaction_flags.length > 0 && (
              <p className="mt-1 text-body-sm">
                <strong>Possible interactions to ask about:</strong> {b.interaction_flags.map((f) => f.names.join(" + ")).join("; ")}
              </p>
            )}
            {b.allergy_warnings.length > 0 && (
              <p className="mt-1 text-body-sm">
                <strong>Allergy notes:</strong> {b.allergy_warnings.map((w) => `${w.medicine} (recorded allergy: ${w.allergen})`).join("; ")}
              </p>
            )}
            {b.glp1_logs.length > 0 && (
              <p className="mt-1 text-body-sm">
                <strong>How I&apos;ve felt on my weekly injection:</strong>{" "}
                {b.glp1_logs.slice(0, 10).map((l) => `${shortDay(l.date)}${l.appetite != null ? ` appetite ${l.appetite}/5` : ""}${l.nausea != null ? ` nausea ${l.nausea}/10` : ""}`).join("; ")}
              </p>
            )}
            <p className="mt-3 text-body-sm text-muted">{b.adherence.message}</p>
            <p className="mt-1 text-body-sm text-muted">Recorded by the patient in the Bubbles app. Not a prescription or medical advice.</p>
          </article>
          <button type="button" onClick={reload} className={`${BTN_TEXT} bubbles-no-print`}>
            Refresh
          </button>
        </div>
      )}
    </QueryView>
  );
}
