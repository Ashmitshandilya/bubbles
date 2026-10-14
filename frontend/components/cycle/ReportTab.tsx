"use client";

// Printable summary for a clinician. "Print or save as PDF" uses window.print(); the embedded print stylesheet hides
// everything except the report root and forces black-on-white.

import { useState, type ReactNode } from "react";
import { BTN_PRIMARY, useBubblesQuery } from "../hub/HubKit";
import { reportPath } from "../../app/lib/cycle-api";
import { confidenceCopy, fmtDay } from "../../app/lib/cycle-format";
import type { Flag, ReportResponse } from "../../app/lib/cycle-types";
import { useCycle, useReloadOnRev } from "./CycleStore";
import { CheckRow } from "./fields";
import { Card, PanelError, PanelSkeleton, TabHeading } from "./shared";

const PRINT_CSS = `
@media print {
  body * { visibility: hidden !important; }
  .cycle-print, .cycle-print * { visibility: visible !important; }
  .cycle-print { position: absolute; inset: 0; margin: 0; padding: 0; border: 0 !important; border-radius: 0 !important; background: #fff !important; color: #000 !important; }
  .cycle-print * { color: #000 !important; background: transparent !important; box-shadow: none !important; border-color: #000 !important; }
  .cycle-print tr, .cycle-print li, .cycle-print dt, .cycle-print dd { break-inside: avoid; page-break-inside: avoid; }
  .cycle-print table { border-collapse: collapse; width: 100%; }
  .cycle-print th, .cycle-print td { border: 1px solid #000 !important; padding: 4px 8px; text-align: left; }
  .cycle-print .no-print { display: none !important; }
  @page { margin: 16mm; }
}
`;

const date = (iso: string | null | undefined) => (iso ? fmtDay(iso, { day: "numeric", month: "short", year: "numeric" }) : "Not enough data");
const num = (n: number | null, unit = "") => (n === null ? "Not enough data" : `${n}${unit}`);

const SEVERITY_WORDS: Record<Flag["severity"], string> = { info: "For information", talk: "Worth discussing", urgent: "Needs prompt attention" };

export function ReportTab() {
  const { today, rev } = useCycle();
  const [months, setMonths] = useState(6);
  const [notes, setNotes] = useState(false);
  const [query, reload] = useBubblesQuery<ReportResponse>(reportPath(months, notes, today));
  useReloadOnRev(reload, rev);

  return (
    <div className="space-y-5">
      <style>{PRINT_CSS}</style>
      <TabHeading id="cycle-h-report" title="Report">A summary of your logs to bring to an appointment. It organises what you recorded and does not diagnose.</TabHeading>

      <Card as="div" className="flex flex-wrap items-end gap-4">
        <div>
          <label htmlFor="cycle-report-months" className="block text-body-sm font-extrabold text-ink">Time covered</label>
          <select id="cycle-report-months" value={months} onChange={(e) => setMonths(Number(e.target.value))} className="mt-2 min-h-[48px] rounded-2xl border border-line bg-surface px-4 text-body text-ink">
            {[3, 6, 12].map((m) => <option key={m} value={m}>Last {m} months</option>)}
          </select>
        </div>
        <CheckRow checked={notes} onChange={setNotes}>Include my notes (off by default)</CheckRow>
        <button type="button" className={BTN_PRIMARY} onClick={() => window.print()} disabled={query.status !== "ready"}>Print or save as PDF</button>
      </Card>

      {query.status === "loading" && <PanelSkeleton rows={3} />}
      {query.status === "error" && <PanelError title="The report didn't load" message={query.message} onRetry={reload} />}
      {query.status === "ready" && <Report r={query.data} />}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-6">
      <h3 className="m-0 mb-2 font-display text-h3 text-ink">{title}</h3>
      {children}
    </section>
  );
}

const TABLE = "w-full border-collapse text-left text-body-sm";
const TH = "border-b-2 border-line px-2 py-2 font-extrabold text-ink";
const TD = "border-b border-line px-2 py-2 text-ink";

function Report({ r }: { r: ReportResponse }) {
  const s = r.summary;
  const rows: Array<[string, string]> = [
    ["Cycles tracked", String(s.cycles_tracked)],
    ["Average cycle length", s.average_length === null ? "Not enough data" : `${s.average_length} days${s.sd !== null ? ` (varies by about ${s.sd} days)` : ""}`],
    ["Shortest and longest", s.shortest !== null && s.longest !== null ? `${s.shortest} and ${s.longest} days` : "Not enough data"],
    ["Average period length", num(s.period_length_average, " days")],
    ["Regularity", s.regularity ? s.regularity.label : "Not enough data"],
    ["Last period started", date(s.last_period_start)],
    ["Next period (estimate)", date(s.next_period_estimate)],
    ["Confidence in estimates", confidenceCopy(s.confidence).label],
  ];

  return (
    <article className="cycle-print rounded-3xl border border-line bg-surface p-5 text-ink sm:p-8" aria-labelledby="cycle-report-title">
      <header>
        <h2 id="cycle-report-title" className="m-0 font-display text-h2">Cycle summary for my clinician</h2>
        <p className="m-0 mt-1 text-body-sm text-muted">
          Prepared with Bubbles on {date(r.generated_on)} · covers {date(r.window.from)} to {date(r.window.to)} ({r.window.months} months) · mode: {r.mode_label}
        </p>
        <p className="m-0 mt-1 text-body-sm text-muted">Organised from my own logs. Not a diagnosis.</p>
      </header>

      <Section title="Summary">
        <table className={TABLE}>
          <caption className="sr-only">Cycle summary</caption>
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}><th scope="row" className={`${TH} w-1/2`}>{k}</th><td className={TD}>{v}</td></tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Cycles">
        {r.cycles.length === 0 ? (
          <p className="m-0 text-body-sm text-muted">No completed cycles in this period.</p>
        ) : (
          <table className={TABLE}>
            <caption className="sr-only">Each cycle in the period</caption>
            <thead><tr><th scope="col" className={TH}>Started</th><th scope="col" className={TH}>Cycle length</th><th scope="col" className={TH}>Period days</th></tr></thead>
            <tbody>
              {r.cycles.map((c) => (
                <tr key={c.start}><td className={TD}>{date(c.start)}</td><td className={TD}>{num(c.length, " days")}</td><td className={TD}>{num(c.period_days, " days")}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <Section title="Symptoms logged">
        {r.symptoms.length === 0 ? (
          <p className="m-0 text-body-sm text-muted">No symptoms logged in this period.</p>
        ) : (
          <table className={TABLE}>
            <caption className="sr-only">How often each symptom was logged</caption>
            <thead><tr><th scope="col" className={TH}>Symptom</th><th scope="col" className={TH}>Days logged</th><th scope="col" className={TH}>Share of logged days</th></tr></thead>
            <tbody>
              {r.symptoms.map((x) => (
                <tr key={x.label}><td className={TD}>{x.label}</td><td className={TD}>{x.days}</td><td className={TD}>{Math.round(x.share <= 1 ? x.share * 100 : x.share)}%</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <Section title="Pain">
        <p className="m-0 text-body-sm text-ink">
          {r.pain.logged_days === 0
            ? "No pain levels logged in this period."
            : `Logged on ${r.pain.logged_days} days. Average ${num(r.pain.average)} of 10, highest ${num(r.pain.maximum)} of 10. Severe pain (a high rating) on ${r.pain.days_at_or_above_severe} ${r.pain.days_at_or_above_severe === 1 ? "day" : "days"}.`}
        </p>
      </Section>

      {r.flags.length > 0 && (
        <Section title="Things worth mentioning">
          <ul className="m-0 list-none space-y-2 p-0">
            {r.flags.map((f) => (
              <li key={f.id} className="rounded-2xl border border-line p-3 text-body-sm">
                <strong>{SEVERITY_WORDS[f.severity]}: {f.title}.</strong> {f.message} {f.detail ?? ""}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.medications.length > 0 && (
        <Section title="Medications I logged">
          <p className="m-0 text-body-sm text-ink">{r.medications.join(", ")}</p>
        </Section>
      )}

      {r.questions_for_clinician.length > 0 && (
        <Section title="Questions I might ask">
          <ol className="m-0 space-y-1 pl-5 text-body-sm text-ink">
            {r.questions_for_clinician.map((q) => <li key={q}>{q}</li>)}
          </ol>
        </Section>
      )}

      {r.notes && r.notes.length > 0 && (
        <Section title="My notes">
          <ul className="m-0 list-none space-y-1 p-0 text-body-sm text-ink">
            {r.notes.map((n, i) => <li key={`${n.date}-${i}`}><strong>{date(n.date)}:</strong> {n.text}</li>)}
          </ul>
        </Section>
      )}

      <footer className="mt-6 border-t-2 border-line pt-3">
        <ul className="m-0 list-none space-y-1 p-0 text-[0.8125rem] text-muted">
          {r.disclaimers.map((d) => <li key={d}>{d}</li>)}
          <li>Predictions are estimates from self-reported logs. They are not birth control and they do not replace medical advice.</li>
        </ul>
      </footer>
    </article>
  );
}
