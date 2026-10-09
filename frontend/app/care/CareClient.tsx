"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { BubblesMascot } from "../../components/BubblesMascot";
import {
  BTN_PRIMARY,
  BTN_SECONDARY,
  CARD,
  ErrorCard,
  HubPage,
  Icon,
  Skeleton,
  TONE,
  humanize,
  toneFor,
  useBubblesQuery,
} from "../../components/hub/HubKit";
import type { Entry } from "../../components/tracking/data";
import { readEntries } from "../lib/api-adapters";
import { formatWhen } from "../lib/dates";
import { mergeRecords, type MedicalSummary } from "./prep";

const DAYS = 180;

interface TimelineEvent {
  id?: string;
  date?: string;
  event_type?: string;
  details?: Record<string, unknown>;
}

interface VisitResponse {
  visit?: {
    visit_summary?: { event_count?: number; frequent_event_types?: Array<[string, number]> };
    timeline?: { events?: TimelineEvent[]; count?: number };
    questions?: string[];
    bring?: string[];
  };
}

interface MedicalResponse {
  summary?: MedicalSummary;
  questions?: string[];
}

const RECORD_LINKS = ["visits", "medications", "conditions", "allergies", "labs", "reports"];

/** First few simple fields of an event, e.g. "Symptom: headache · Severity: 6". */
function describe(details: Record<string, unknown> | undefined): string {
  return Object.entries(details ?? {})
    .filter(([key, value]) => ["string", "number", "boolean"].includes(typeof value) && value !== "" && !/(^|_)(id|source|user)/.test(key))
    .slice(0, 3)
    .map(([key, value]) => `${humanize(key)}: ${String(value)}`)
    .join(" · ");
}

export function CareClient() {
  return (
    <HubPage title="Doctor prep">
      <DoctorPrep />
    </HubPage>
  );
}

function DoctorPrep() {
  const [draft, setDraft] = useState("");
  const [concern, setConcern] = useState("");
  const [visitQuery, reloadVisit] = useBubblesQuery<VisitResponse>("/doctor/prepare", { days: DAYS, concern: concern || undefined });
  const [medicalQuery, reloadMedical] = useBubblesQuery<MedicalResponse>("/medical/summary", { days: DAYS });
  // The Labs and Reports pages' own lists: /medical/summary cannot see entries saved in compatibility mode.
  const [labsQuery, reloadLabs] = useBubblesQuery<{ entries?: unknown }>("/health/labs?days=730");
  const [reportsQuery, reloadReports] = useBubblesQuery<{ entries?: unknown }>("/health/reports?days=730");
  const [showAll, setShowAll] = useState(false);
  const [copyStatus, setCopyStatus] = useState("");

  const visit = visitQuery.status === "ready" ? visitQuery.data.visit ?? {} : null;
  const medical = medicalQuery.status === "ready" ? medicalQuery.data : null;
  const labEntries = labsQuery.status === "ready" ? readEntries<Entry>(labsQuery.data.entries) : null;
  const reportEntries = reportsQuery.status === "ready" ? readEntries<Entry>(reportsQuery.data.entries) : null;
  const records = medical || labEntries || reportEntries ? mergeRecords(medical?.summary, labEntries, reportEntries) : null;
  const recordsLoading = [medicalQuery, labsQuery, reportsQuery].some((q) => q.status === "loading");
  const reloadRecords = () => {
    reloadMedical();
    reloadLabs();
    reloadReports();
  };
  const questions = [...new Set([...(visit?.questions ?? []), ...(medical?.questions ?? [])])];
  const events = visit?.timeline?.events ?? [];
  const eventCount = visit?.visit_summary?.event_count ?? visit?.timeline?.count ?? events.length;
  const frequent = (visit?.visit_summary?.frequent_event_types ?? []).slice(0, 4);
  const flagged = records?.flagged ?? [];

  function submitConcern(event: FormEvent) {
    event.preventDefault();
    setConcern(draft.trim());
  }

  async function copySummary() {
    const lines = [
      `Visit summary prepared with Bubbles — ${formatWhen(new Date().toISOString(), true)}`,
      "Organized from my own logs. Not a diagnosis.",
      ...(concern ? [`What I want to discuss: ${concern}`] : []),
      `Logs in the last 6 months: ${eventCount}${frequent.length ? ` (most often: ${frequent.map(([t, n]) => `${humanize(t)} ${n}`).join(", ")})` : ""}`,
      "",
      "Questions:",
      ...questions.map((q, i) => `${i + 1}. ${q}`),
      ...(visit?.bring?.length ? ["", "To bring:", ...visit.bring.map((b) => `- ${b}`)] : []),
      ...(flagged.length
        ? ["", "Lab results outside the reference range (flagged by the lab, or against the range entered; not interpreted by Bubbles):", ...flagged.map((l) => `- ${l.label}: ${l.flag}${l.value != null ? ` (${l.value}${l.unit ? ` ${l.unit}` : ""})` : ""}`)]
        : []),
      ...(events.length
        ? ["", "Recent timeline:", ...events.slice(0, 20).map((e) => `- ${formatWhen(e.date, true)} · ${humanize(e.event_type ?? "entry")}${describe(e.details) ? ` · ${describe(e.details)}` : ""}`)]
        : []),
    ];
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopyStatus("Copied — paste it into an email or your notes.");
    } catch {
      setCopyStatus("Copying isn't allowed in this browser. Try Print instead.");
    }
  }

  return (
    <div className="space-y-8">
      {/* Print only the prepared summary, not the app chrome. */}
      <style>{`@media print{body *{visibility:hidden!important}#care-print,#care-print *{visibility:visible!important}#care-print{position:absolute;left:0;top:0;width:100%}}`}</style>

      <header className="bubbles-rise flex flex-wrap items-center gap-4">
        <div className="flex h-[72px] w-[72px] items-center justify-center rounded-[24px] bg-tint-sky">
          <BubblesMascot size={60} mood="calm" animated={false} />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-h1 text-ink">Doctor prep</h1>
          <p className="mt-1 text-body font-semibold text-muted">Walk into your next appointment with your story organized.</p>
        </div>
      </header>

      <div className="flex items-start gap-3 rounded-3xl bg-tint-sky p-5 text-bubbles-sky-deep">
        <span className="shrink-0"><Icon id="shield" /></span>
        <p className="text-body font-bold">
          Bubbles doesn&apos;t diagnose. It organizes what you&apos;ve logged and suggests questions — your clinician makes the
          call.
        </p>
      </div>

      <form onSubmit={submitConcern} className={`${CARD} flex flex-wrap items-end gap-3 p-5`}>
        <div className="min-w-[220px] flex-1">
          <label htmlFor="concern" className="block text-body-sm font-extrabold text-ink">
            What would you like to talk about? <span className="font-semibold text-muted">(optional)</span>
          </label>
          <input
            id="concern"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={200}
            placeholder="e.g. headaches before my period"
            className="mt-2 min-h-[48px] w-full rounded-2xl border-2 border-line bg-surface px-4 text-body text-ink focus:border-bubbles-grape focus:outline-none"
          />
        </div>
        <button type="submit" className={BTN_PRIMARY}>
          {concern && concern === draft.trim() ? "Updated" : "Prepare"}
        </button>
      </form>

      <section id="care-print" aria-labelledby="prep-title" className="space-y-6">
        <h2 id="prep-title" className="sr-only">
          Your visit summary
        </h2>
        <div className="hidden print:block">
          <p className="text-h3">Visit summary prepared with Bubbles · {formatWhen(new Date().toISOString(), true)}</p>
          <p>Organized from my own logs over the last 6 months. Not a diagnosis.{concern ? ` Topic: ${concern}.` : ""}</p>
        </div>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <div className={`${CARD} p-5 sm:p-6`}>
            <h3 className="text-h3 text-ink">Questions to ask</h3>
            <p className="mt-1 text-body-sm text-muted">Pick the ones that fit — you don&apos;t need to ask them all.</p>
            {visitQuery.status === "loading" && <Skeleton className="mt-4 h-40" />}
            {visitQuery.status === "error" && (
              <div className="mt-4">
                <ErrorCard title="Questions didn't load" message={visitQuery.message} onRetry={reloadVisit} inset />
              </div>
            )}
            {questions.length > 0 && (
              <ol className="bubbles-stagger m-0 mt-4 list-none space-y-3 p-0">
                {questions.map((question, i) => (
                  <li key={question} className="flex gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-tint-sun font-display font-semibold text-bubbles-sun-deep">
                      {i + 1}
                    </span>
                    <span className="pt-1 text-body text-ink">{question}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="space-y-6">
            {visit?.bring?.length ? (
              <div className={`${CARD} p-5 sm:p-6`}>
                <h3 className="text-h3 text-ink">What to bring</h3>
                <ul className="m-0 mt-3 list-none space-y-2 p-0">
                  {visit.bring.map((item) => (
                    <li key={item} className="flex items-start gap-2 text-body text-ink">
                      <span className="mt-2 h-2.5 w-2.5 shrink-0 rounded-full bg-bubbles-mint" aria-hidden="true" />
                      {humanize(item)}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className={`${CARD} p-5 sm:p-6`}>
              <h3 className="text-h3 text-ink">Records on file</h3>
              {recordsLoading && <Skeleton className="mt-3 h-20" />}
              {!recordsLoading && !records && (
                <div className="mt-3">
                  <ErrorCard title="Records didn't load" message={medicalQuery.status === "error" ? medicalQuery.message : "Bubbles can't reach the server right now."} onRetry={reloadRecords} inset />
                </div>
              )}
              {!recordsLoading && records && (
                <>
                  <p className="mt-1 text-body text-muted">
                    {records.reportCount} reports · {records.labCount} lab results
                  </p>
                  {flagged.length > 0 ? (
                    <>
                      <ul className="m-0 mt-3 list-none space-y-2 p-0">
                        {flagged.map((lab, i) => (
                          <li key={`${lab.label}-${i}`} className="rounded-2xl bg-blush px-3 py-2 text-body-sm">
                            <span className="font-bold text-ink">{lab.label}</span>{" "}
                            <span className="text-muted">
                              flagged {lab.flag}
                              {lab.value != null ? ` · ${lab.value}${lab.unit ? ` ${lab.unit}` : ""}` : ""}
                            </span>
                          </li>
                        ))}
                      </ul>
                      <p className="mt-2 text-[0.8125rem] text-muted">Flagged by the lab, or outside the range you entered. Bubbles doesn&apos;t interpret results — ask your clinician.</p>
                    </>
                  ) : (
                    <p className="mt-2 text-body-sm text-muted">No lab results flagged in what you&apos;ve added.</p>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        <div className={`${CARD} p-5 sm:p-6`}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-h3 text-ink">Your recent timeline</h3>
            {visit && <p className="text-body-sm font-bold text-muted">{eventCount} logs · last 6 months</p>}
          </div>
          {frequent.length > 0 && (
            <p className="mt-1 text-body-sm text-muted">
              Most often: {frequent.map(([type, n]) => `${humanize(type)} (${n})`).join(", ")}
            </p>
          )}
          {visitQuery.status === "loading" && <Skeleton className="mt-4 h-48" />}
          {visitQuery.status === "error" && (
            <p className="mt-3 text-body-sm text-muted">Your timeline loads together with the questions above — try again there.</p>
          )}
          {visit && events.length === 0 && (
            <div className="mt-4 flex flex-wrap items-center gap-4 rounded-3xl bg-blush p-5">
              <BubblesMascot size={52} mood="resting" animated={false} />
              <p className="min-w-0 flex-1 text-body text-muted">
                No logs in the last 6 months yet. As you log symptoms, sleep or your cycle, Bubbles builds this timeline for
                you.
              </p>
            </div>
          )}
          {events.length > 0 && (
            <ol className="m-0 mt-4 list-none space-y-0 border-l-2 border-line p-0 pl-5">
              {events.map((event, i) => {
                const tone = TONE[toneFor(event.event_type ?? "")];
                const detail = describe(event.details);
                return (
                  <li key={event.id ?? i} className={`relative pb-4 ${i >= 10 && !showAll ? "hidden print:block" : ""}`}>
                    <span className={`absolute -left-[27px] top-1.5 h-3 w-3 rounded-full ring-4 ring-white ${tone.dot}`} aria-hidden="true" />
                    <p className="text-[0.8125rem] font-bold text-muted">{formatWhen(event.date, true)}</p>
                    <p className="font-extrabold text-ink">{humanize(event.event_type ?? "Entry")}</p>
                    {detail && <p className="break-words text-body-sm text-muted">{detail}</p>}
                  </li>
                );
              })}
            </ol>
          )}
          {events.length > 10 && (
            <button type="button" onClick={() => setShowAll((v) => !v)} className={`${BTN_SECONDARY} mt-2 print:hidden`} aria-expanded={showAll}>
              {showAll ? "Show fewer" : `Show all ${events.length}`}
            </button>
          )}
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={copySummary} disabled={!visit} className={BTN_PRIMARY}>
          Copy summary
        </button>
        <button type="button" onClick={() => window.print()} disabled={!visit} className={BTN_SECONDARY}>
          Print
        </button>
        <p role="status" className="text-body-sm font-bold text-muted">
          {copyStatus}
        </p>
      </div>

      <section aria-labelledby="records-title">
        <h2 id="records-title" className="text-h3 text-ink">
          Keep your records up to date
        </h2>
        <ul className="m-0 mt-3 flex list-none flex-wrap gap-2 p-0">
          {RECORD_LINKS.map((id) => (
            <li key={id}>
              <Link
                href={`/${id}`}
                className="bubbles-press inline-flex min-h-[44px] items-center gap-2 rounded-full border-2 border-line bg-surface px-4 text-body-sm font-extrabold text-bubbles-sky-deep no-underline hover:border-line-strong"
              >
                <Icon id={id} size={18} />
                {id === "labs" ? "Lab results" : humanize(id)}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
