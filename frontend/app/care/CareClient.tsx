"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import { BubblesMascot } from "../../components/BubblesMascot";
import {
  BTN_PRIMARY,
  BTN_SECONDARY,
  CARD,
  SECTION,
  ErrorCard,
  HubPage,
  Icon,
  PILL,
  Skeleton,
  TONE,
  humanize,
  toneFor,
  useBubblesQuery,
  type Query,
} from "../../components/hub/HubKit";
import type { Entry } from "../../components/tracking/data";
import { readEntries } from "../lib/api-adapters";
import { noteForLab, readLabNotes, type LabNote } from "../lib/nutrients";
import { formatWhen } from "../lib/dates";
import {
  QUESTION_MAX,
  addQuestion,
  afterDay,
  mergeRecords,
  questionsText,
  recordRows,
  summaryText,
  typeCounts,
  visitLabel,
  visitSplit,
  whenText,
  type MedicalSummary,
  type RangeStatus,
  type RecordKind,
} from "./prep";

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

type EntriesResponse = { entries?: unknown };

const RANGE_BADGE: Record<Exclude<RangeStatus, "none">, { text: string; style: string }> = {
  within: { text: "Within range entered", style: "bg-tint-mint text-bubbles-mint-deep" },
  below: { text: "Below range entered", style: "bg-tint-sun text-bubbles-sun-deep" },
  above: { text: "Above range entered", style: "bg-tint-sun text-bubbles-sun-deep" },
};

const RECORD_SECTIONS: Array<{ kind: RecordKind; title: string; icon: string; empty: string; add: string }> = [
  { kind: "medications", title: "Medicines", icon: "medications", empty: "No medicines added yet.", add: "Add a medicine" },
  { kind: "conditions", title: "Conditions", icon: "conditions", empty: "No conditions added yet.", add: "Add a condition" },
  { kind: "allergies", title: "Allergies", icon: "allergies", empty: "No allergies added yet. That is not the same as having none.", add: "Add an allergy" },
  { kind: "labs", title: "Lab results", icon: "labs", empty: "No lab results added yet.", add: "Add a lab result" },
  { kind: "reports", title: "Reports", icon: "reports", empty: "No reports added yet.", add: "Add a report" },
  { kind: "visits", title: "Visits", icon: "visits", empty: "No visits added yet.", add: "Log a visit" },
];

const SKIP_KEYS = /^(name|category|date|type|kind)$/;
const NAME_KEYS = /^(symptom|condition_name|allergen|medication|test_name|description|activity|meal)$/;

/** First few simple fields of an event, e.g. "Headache · Severity: 6": the name on its own, other fields labelled. */
function describe(details: Record<string, unknown> | undefined): string {
  return Object.entries(details ?? {})
    .filter(([key, value]) => ["string", "number", "boolean"].includes(typeof value) && value !== "" && !SKIP_KEYS.test(key) && !/(^|_)(id|source|user)/.test(key))
    .sort(([a], [b]) => Number(NAME_KEYS.test(b)) - Number(NAME_KEYS.test(a)))
    .slice(0, 3)
    .map(([key, value]) => (NAME_KEYS.test(key) ? humanize(String(value)) : `${humanize(key)}: ${String(value)}`))
    .join(" · ");
}

/** A closed row that opens on tap, and opens itself while printing so a printed summary still has everything in it. */
function Fold({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    let was = false;
    const before = () => {
      was = ref.current?.open ?? false;
      if (ref.current) ref.current.open = true;
    };
    const after = () => {
      if (ref.current) ref.current.open = was;
    };
    window.addEventListener("beforeprint", before);
    window.addEventListener("afterprint", after);
    return () => {
      window.removeEventListener("beforeprint", before);
      window.removeEventListener("afterprint", after);
    };
  }, []);
  return (
    <details ref={ref} className="group rounded-[24px] border border-line bg-surface shadow-sm">
      <summary className="flex min-h-[56px] cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 [&::-webkit-details-marker]:hidden">
        <span className="font-display text-h4 text-ink">{title}</span>
        <span className="flex items-center gap-2 text-body-sm font-bold text-muted">
          {hint}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="transition-transform group-open:rotate-90"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
        </span>
      </summary>
      <div className="space-y-3 px-4 pb-5 pt-1 sm:px-5">{children}</div>
    </details>
  );
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

async function copyText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

const noSubscribe = () => () => undefined;

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
  // The tracker pages' own lists: /medical/summary cannot see entries saved in compatibility mode.
  const [labsQuery, reloadLabs] = useBubblesQuery<EntriesResponse>("/health/labs?days=730");
  const [reportsQuery, reloadReports] = useBubblesQuery<EntriesResponse>("/health/reports?days=730");
  const [visitsQuery, reloadVisits] = useBubblesQuery<EntriesResponse>("/health/visits?days=730");
  const [medsQuery, reloadMeds] = useBubblesQuery<EntriesResponse>("/health/medications?days=730");
  const [conditionsQuery, reloadConditions] = useBubblesQuery<EntriesResponse>("/health/conditions?days=730");
  const [allergiesQuery, reloadAllergies] = useBubblesQuery<EntriesResponse>("/health/allergies?days=730");
  // Plain notes on logged results (an extra: if it does not load, the badges alone stay).
  const [nutrientQuery] = useBubblesQuery<unknown>("/nutrients/nudges");
  const labNotes = nutrientQuery.status === "ready" ? readLabNotes(nutrientQuery.data) : [];
  const [showAll, setShowAll] = useState(false);
  const [copyStatus, setCopyStatus] = useState("");
  const [skipped, setSkipped] = useState<ReadonlySet<string>>(new Set());
  const [own, setOwn] = useState<string[]>([]);
  const [ownDraft, setOwnDraft] = useState("");
  const [questionStatus, setQuestionStatus] = useState("");
  const canShare = useSyncExternalStore(noSubscribe, () => typeof navigator.share === "function", () => false);

  const visit = visitQuery.status === "ready" ? visitQuery.data.visit ?? {} : null;
  const medical = medicalQuery.status === "ready" ? medicalQuery.data : null;
  const entriesOf = (q: Query<EntriesResponse>) => (q.status === "ready" ? readEntries<Entry>(q.data.entries) : null);
  const labEntries = entriesOf(labsQuery);
  const reportEntries = entriesOf(reportsQuery);
  const visitEntries = entriesOf(visitsQuery);
  const lists: Record<RecordKind, Entry[] | null> = {
    medications: entriesOf(medsQuery),
    conditions: entriesOf(conditionsQuery),
    allergies: entriesOf(allergiesQuery),
    labs: labEntries,
    reports: reportEntries,
    visits: visitEntries,
  };
  const queries: Record<RecordKind, [Query<EntriesResponse>, () => void]> = {
    medications: [medsQuery, reloadMeds],
    conditions: [conditionsQuery, reloadConditions],
    allergies: [allergiesQuery, reloadAllergies],
    labs: [labsQuery, reloadLabs],
    reports: [reportsQuery, reloadReports],
    visits: [visitsQuery, reloadVisits],
  };
  const records = medical || labEntries || reportEntries ? mergeRecords(medical?.summary, labEntries, reportEntries) : null;
  const flagged = records?.flagged ?? [];

  const serverQuestions = [...new Set([...(visit?.questions ?? []), ...(medical?.questions ?? [])])];
  const allQuestions = [...serverQuestions, ...own.filter((q) => !serverQuestions.includes(q))];
  const picked = allQuestions.filter((q) => !skipped.has(q));
  const events = visit?.timeline?.events ?? [];
  const eventCount = visit?.visit_summary?.event_count ?? visit?.timeline?.count ?? events.length;
  const frequent = (visit?.visit_summary?.frequent_event_types ?? []).slice(0, 4);

  const { last, next } = visitEntries ? visitSplit(visitEntries) : { last: null, next: null };
  const sinceEvents = last ? afterDay(events, last.date) : events;
  const sinceTypes = typeCounts(sinceEvents).slice(0, 5);
  const added = last
    ? ([
        ["medicine", "medicines", lists.medications],
        ["condition", "conditions", lists.conditions],
        ["allergy", "allergies", lists.allergies],
        ["lab result", "lab results", lists.labs],
        ["report", "reports", lists.reports],
      ] as const).flatMap(([one, many, list]) => {
        const n = list ? afterDay(list, last.date).length : 0;
        return n ? [plural(n, one, many)] : [];
      })
    : [];
  const visitText = (v: Entry | null) => (v ? [whenText(v.date), visitLabel(v)].filter(Boolean).join(" · ") : null);

  function submitConcern(event: FormEvent) {
    event.preventDefault();
    setConcern(draft.trim());
  }

  function toggleQuestion(question: string) {
    setQuestionStatus("");
    setSkipped((prev) => {
      const next = new Set(prev);
      if (next.has(question)) next.delete(question);
      else next.add(question);
      return next;
    });
  }

  function submitOwn(event: FormEvent) {
    event.preventDefault();
    setOwn((prev) => addQuestion(prev, ownDraft));
    setOwnDraft("");
    setQuestionStatus("");
  }

  async function share(body: string, title: string, setStatus: (s: string) => void) {
    try {
      await navigator.share({ title, text: body });
    } catch (error) {
      // Closing the share sheet is a choice, not a failure.
      if (!(error instanceof DOMException && error.name === "AbortError")) setStatus("Sharing didn't work here. Use Copy instead.");
    }
  }

  const summary = () =>
    summaryText({
      generatedOn: formatWhen(new Date().toISOString(), true),
      concern,
      lastVisit: visitText(last),
      nextVisit: visitText(next),
      logLine: `Logs in the last 6 months: ${eventCount}${frequent.length ? ` (most often: ${frequent.map(([t, n]) => `${humanize(t)} ${n}`).join(", ")})` : ""}`,
      sinceLine: last ? `Since that visit: ${[plural(sinceEvents.length, "log"), ...added.map((a) => `${a} added`)].join(", ")}` : null,
      questions: picked,
      bring: visit?.bring?.map(humanize) ?? [],
      flagged: flagged.map((l) => `${l.label}: ${l.flag}${l.value != null ? ` (${l.value}${l.unit ? ` ${l.unit}` : ""})` : ""}`),
      lists: (
        [
          ["Medicines I log (as I entered them)", "medications"],
          ["Conditions I log", "conditions"],
          ["Allergies I log", "allergies"],
        ] as const
      ).map(([heading, kind]) => ({ heading, rows: recordRows(kind, lists[kind] ?? []).map((r) => [r.title, r.meta].filter(Boolean).join(" · ")) })),
      timeline: events.slice(0, 20).map((e) => `${whenText(e.date)} · ${humanize(e.event_type ?? "entry")}${describe(e.details) ? ` · ${describe(e.details)}` : ""}`),
    });

  async function copySummary() {
    setCopyStatus((await copyText(summary())) ? "Summary copied. Paste it into an email or your notes." : "Copying isn't allowed in this browser. Try Print instead.");
  }

  async function copyQuestions() {
    setQuestionStatus((await copyText(questionsText(picked))) ? `Copied ${plural(picked.length, "question")}.` : "Copying isn't allowed in this browser. Select the text and copy it by hand.");
  }

  const visitsLoading = visitsQuery.status === "loading";

  return (
    <div className="space-y-8">
      {/* Print only the prepared summary, not the app chrome. */}
      <style>{`@media print{body *{visibility:hidden!important}#care-print,#care-print *{visibility:visible!important}#care-print{position:absolute;left:0;top:0;width:100%}}`}</style>

      <div id="care-print" className="space-y-6">
        <div className="hidden print:block">
          <p className="text-h3">Visit summary prepared with Bubbles · {formatWhen(new Date().toISOString(), true)}</p>
          <p>Organized from my own logs over the last 6 months. Not a diagnosis.{concern ? ` Topic: ${concern}.` : ""}</p>
        </div>

        {/* Visit-ready summary: what changed since the last visit, from data already on file. */}
        <section aria-labelledby="ready-title" className="bubbles-rise rounded-[24px] bg-tint-sky p-5 text-ink sm:p-8">
          <div className="flex flex-wrap items-start gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-label text-bubbles-sky-deep">Doctor prep</p>
              <h1 id="ready-title" className="mt-1 text-h1 text-ink">
                Your visit-ready summary
              </h1>
              <p className="mt-1 text-body font-semibold text-bubbles-sky-deep">
                From your own logs. Not a diagnosis.
              </p>
            </div>
          </div>

          <dl className="m-0 mt-6 grid divide-y divide-line overflow-hidden rounded-[20px] border border-line bg-surface sm:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)] sm:divide-x sm:divide-y-0">
            <VisitTile label="Last visit" value={visitText(last)} loading={visitsLoading} failed={visitsQuery.status === "error"} onRetry={reloadVisits} gap="No visit logged yet" />
            <VisitTile label="Next visit" value={visitText(next)} loading={visitsLoading} failed={false} onRetry={reloadVisits} gap="No upcoming visit logged" />
            <div className="p-4">
              <dt className="text-body-sm font-extrabold text-ink-soft">{last ? "Logged since last visit" : "Logged in the last 6 months"}</dt>
              <dd className="m-0 mt-1">
                {visitQuery.status === "loading" ? (
                  <Skeleton className="h-8 w-24" />
                ) : visit ? (
                  <span className="font-display text-h3 text-ink">{plural(sinceEvents.length, "log")}</span>
                ) : (
                  <span className="text-body-sm text-muted">Didn&apos;t load</span>
                )}
              </dd>
            </div>
          </dl>

          <div className="mt-5">
            <h2 className="text-h4 text-ink">{last ? "What changed since then" : "What you logged lately"}</h2>
            {!last && !visitsLoading && (
              <p className="mt-1 text-body-sm text-bubbles-sky-deep">
                No visit is logged, so there is no &ldquo;since&rdquo; yet. This shows the last 6 months.{" "}
                <Link href="/visits" className="font-extrabold text-bubbles-sky-deep underline">
                  Log a visit
                </Link>
              </p>
            )}
            {visit && sinceTypes.length === 0 && added.length === 0 ? (
              <p className="mt-2 text-body text-ink-soft">{last ? "Nothing new logged since that visit." : "No logs in the last 6 months."}</p>
            ) : (
              <ul className="m-0 mt-3 flex list-none flex-wrap gap-2 p-0">
                {sinceTypes.map(([type, n]) => (
                  <li key={type} className={`${PILL} ${TONE[toneFor(type)].chip}`}>
                    {humanize(type)} · {n}
                  </li>
                ))}
                {added.map((a) => (
                  <li key={a} className={`${PILL} bg-surface text-ink`}>
                    {a} added
                  </li>
                ))}
              </ul>
            )}
            {flagged.length > 0 && (
              <p className="mt-3 text-body-sm font-bold text-ink">
                {plural(flagged.length, "lab result")} outside the range entered. Bubbles doesn&apos;t interpret results. Ask your clinician.
              </p>
            )}
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3 print:hidden">
            <button type="button" onClick={copySummary} disabled={!visit} className={BTN_PRIMARY}>
              Copy summary
            </button>
            {canShare && (
              <button type="button" onClick={() => share(summary(), "Visit summary from Bubbles", setCopyStatus)} disabled={!visit} className={BTN_SECONDARY}>
                Share
              </button>
            )}
            <button type="button" onClick={() => window.print()} disabled={!visit} className={BTN_SECONDARY}>
              Print
            </button>
            <p role="status" className="text-body-sm font-bold text-bubbles-sky-deep">
              {copyStatus}
            </p>
          </div>
        </section>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          {/* Questions */}
          <section aria-labelledby="questions-title" className={`${SECTION}`}>
            <h2 id="questions-title" className="text-h3 text-ink">
              Questions to ask
            </h2>
            <p className="mt-1 text-body-sm text-muted">Untick any you don&apos;t need.</p>
            {visitQuery.status === "loading" && <Skeleton className="mt-4 h-40" />}
            {visitQuery.status === "error" && (
              <div className="mt-4">
                <ErrorCard title="Questions didn't load" message={visitQuery.message} onRetry={reloadVisit} inset />
              </div>
            )}
            {allQuestions.length > 0 && (
              <ul className="m-0 mt-4 list-none space-y-2 p-0">
                {allQuestions.map((question, i) => {
                  const on = !skipped.has(question);
                  return (
                    <li key={question}>
                      <label className={`flex min-h-[48px] cursor-pointer items-start gap-3 rounded-2xl px-3 py-2 ${on ? "bg-tint-grape" : "bg-blush"}`}>
                        <input type="checkbox" checked={on} onChange={() => toggleQuestion(question)} className="mt-1 h-6 w-6 shrink-0 accent-[var(--bubbles-grape)]" />
                        <span className={`pt-0.5 text-body ${on ? "text-ink" : "text-muted"}`}>
                          <span className="sr-only">Question {i + 1}: </span>
                          {question}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}

            <form onSubmit={submitOwn} className="mt-4 flex flex-wrap items-end gap-3 print:hidden">
              <div className="min-w-[200px] flex-1">
                <label htmlFor="own-question" className="block text-body-sm font-extrabold text-ink">
                  Add your own question
                </label>
                <input
                  id="own-question"
                  value={ownDraft}
                  onChange={(e) => setOwnDraft(e.target.value)}
                  maxLength={QUESTION_MAX}
                  className="mt-2 min-h-[48px] w-full rounded-2xl border border-line bg-surface px-4 text-body text-ink focus:border-bubbles-grape focus:outline-none"
                />
              </div>
              <button type="submit" disabled={!ownDraft.trim()} className={BTN_SECONDARY}>
                Add
              </button>
            </form>

            <div className="mt-5 flex flex-wrap items-center gap-3 print:hidden">
              <button type="button" onClick={copyQuestions} disabled={picked.length === 0} className={BTN_PRIMARY}>
                Copy questions
              </button>
              {canShare && (
                <button type="button" onClick={() => share(questionsText(picked), "Questions for my visit", setQuestionStatus)} disabled={picked.length === 0} className={BTN_SECONDARY}>
                  Share
                </button>
              )}
              <p role="status" className="text-body-sm font-bold text-muted">
                {questionStatus}
              </p>
            </div>
          </section>

          <div className="space-y-6">
            <form onSubmit={submitConcern} className={`${CARD} space-y-3 p-5 print:hidden`}>
              <label htmlFor="concern" className="block text-body-sm font-extrabold text-ink">
                What would you like to talk about? <span className="font-semibold text-muted">(optional)</span>
              </label>
              <input
                id="concern"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                maxLength={200}
                placeholder="e.g. headaches before my period"
                className="min-h-[48px] w-full rounded-2xl border border-line bg-surface px-4 text-body text-ink focus:border-bubbles-grape focus:outline-none"
              />
              <button type="submit" className={BTN_PRIMARY}>
                {concern && concern === draft.trim() ? "Updated" : "Prepare"}
              </button>
            </form>

            <Fold title="What to bring">
              {visit?.bring?.length ? (
                <ul className="m-0 list-none space-y-2 p-0">
                  {visit.bring.map((item) => (
                    <li key={item} className="flex items-start gap-2 text-body text-ink">
                      <span className="mt-2 h-2.5 w-2.5 shrink-0 rounded-full bg-bubbles-mint" aria-hidden="true" />
                      {humanize(item)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="m-0 text-body-sm text-muted">{visit ? "Nothing suggested yet. Bring a list of your medicines and any recent results." : "Loads together with the questions."}</p>
              )}
            </Fold>
          </div>
        </div>

        {/* Records on file: each one scannable, each one a gap when empty. */}
        <Fold title="Records on file">
          <div className="flex flex-col gap-2">
            {RECORD_SECTIONS.map((section) => (
              <RecordCard key={section.kind} section={section} entries={lists[section.kind]} query={queries[section.kind][0]} onRetry={queries[section.kind][1]} labNotes={labNotes} />
            ))}
          </div>
          {medicalQuery.status === "error" && labEntries === null && reportEntries === null && (
            <ErrorCard title="Record counts didn't load" message={medicalQuery.message} onRetry={reloadMedical} inset />
          )}
        </Fold>

        <Fold title="Your recent timeline" hint={visit ? plural(eventCount, "log") : undefined}>
          {frequent.length > 0 && <p className="mt-1 text-body-sm text-muted">Most often: {frequent.map(([type, n]) => `${humanize(type)} (${n})`).join(", ")}</p>}
          {visitQuery.status === "loading" && <Skeleton className="mt-4 h-48" />}
          {visitQuery.status === "error" && <p className="mt-3 text-body-sm text-muted">Your timeline loads together with the questions above. Try again there.</p>}
          {visit && events.length === 0 && (
            <div className="mt-4 flex flex-wrap items-center gap-4 rounded-3xl bg-blush p-5">
              <BubblesMascot size={52} mood="resting" animated={false} />
              <p className="min-w-0 flex-1 text-body text-muted">No logs in the last 6 months yet. As you log symptoms, sleep or your cycle, Bubbles builds this timeline for you.</p>
            </div>
          )}
          {events.length > 0 && (
            <ol className="m-0 mt-4 list-none space-y-0 border-l-2 border-line p-0 pl-5">
              {events.map((event, i) => {
                const tone = TONE[toneFor(event.event_type ?? "")];
                const detail = describe(event.details);
                return (
                  <li key={event.id ?? i} className={`relative pb-4 ${i >= 6 && !showAll ? "hidden print:block" : ""}`}>
                    <span className={`absolute -left-[27px] top-1.5 h-3 w-3 rounded-full ring-4 ring-white ${tone.dot}`} aria-hidden="true" />
                    <p className="text-chip font-bold text-muted">{whenText(event.date)}</p>
                    <p className="font-extrabold text-ink">{humanize(event.event_type ?? "Entry")}</p>
                    {detail && <p className="break-words text-body-sm text-muted">{detail}</p>}
                  </li>
                );
              })}
            </ol>
          )}
          {events.length > 6 && (
            <button type="button" onClick={() => setShowAll((v) => !v)} className={`${BTN_SECONDARY} mt-2 print:hidden`} aria-expanded={showAll}>
              {showAll ? "Show fewer" : `Show all ${events.length}`}
            </button>
          )}
        </Fold>
      </div>
    </div>
  );
}

function VisitTile({ label, value, loading, failed, onRetry, gap }: { label: string; value: string | null; loading: boolean; failed: boolean; onRetry: () => void; gap: string }) {
  return (
    <div className="p-4">
      <dt className="text-body-sm font-extrabold text-ink-soft">{label}</dt>
      <dd className="m-0 mt-1 break-words">
        {loading ? (
          <Skeleton className="h-8 w-32" />
        ) : failed ? (
          <button type="button" onClick={onRetry} className="text-body-sm font-extrabold text-bubbles-sky-deep underline print:hidden">
            Didn&apos;t load. Try again
          </button>
        ) : value ? (
          <span className="font-bold text-ink">{value}</span>
        ) : (
          <span className="text-body-sm text-muted">{gap}</span>
        )}
      </dd>
    </div>
  );
}

/** The server's plain note under a lab row's badge. A result inside its range needs no second sentence; a missing range stays a gap. */
function LabNoteLine({ note, fallbackGap }: { note: LabNote | null; fallbackGap: boolean }) {
  if (!note) return fallbackGap ? <p className="mt-1 text-chip text-muted">No range entered, so nothing to compare.</p> : null;
  if (note.status === "within") return null;
  return (
    <p data-private className="mt-1 text-chip text-muted">
      {note.text}
      {note.ask ? ` ${note.ask}` : ""}
    </p>
  );
}

function RecordCard({
  section,
  entries,
  query,
  onRetry,
  labNotes,
}: {
  section: (typeof RECORD_SECTIONS)[number];
  entries: Entry[] | null;
  query: Query<EntriesResponse>;
  onRetry: () => void;
  labNotes: readonly LabNote[];
}) {
  const rows = entries ? recordRows(section.kind, entries) : [];
  const shown = rows.slice(0, 4);
  return (
    <section aria-labelledby={`rec-${section.kind}`} className={`${SECTION} flex flex-col`}>
      <div className="flex items-center gap-2 text-bubbles-sky-deep">
        <span className="shrink-0">
          <Icon id={section.icon} />
        </span>
        <h3 id={`rec-${section.kind}`} className="text-h4 text-ink">
          {section.title}
        </h3>
        {entries && <span className="ml-auto text-body-sm font-bold text-muted">{rows.length}</span>}
      </div>
      <div className="mt-3 flex-1">
        {query.status === "loading" && <Skeleton className="h-20" />}
        {query.status === "error" && (
          <p className="text-body-sm text-muted">
            Didn&apos;t load.{" "}
            <button type="button" onClick={onRetry} className="font-extrabold text-bubbles-sky-deep underline">
              Try again
            </button>
          </p>
        )}
        {entries && rows.length === 0 && <p className="text-body-sm text-muted">{section.empty}</p>}
        {shown.length > 0 && (
          <ul className="m-0 list-none divide-y-2 divide-line p-0">
            {shown.map((row) => (
              <li key={row.id} className="py-2">
                <p className="break-words font-bold text-ink">{row.title}</p>
                {row.meta && <p className="break-words text-body-sm text-muted">{row.meta}</p>}
                {row.range && row.range.status !== "none" && (
                  <p className="mt-1 flex flex-wrap items-center gap-2">
                    <span className={`${PILL} ${RANGE_BADGE[row.range.status].style}`}>{RANGE_BADGE[row.range.status].text}</span>
                    <span className="text-chip text-muted">Range entered: {row.range.range}</span>
                  </p>
                )}
                <LabNoteLine note={section.kind === "labs" ? noteForLab(labNotes, row.title, row.date) : null} fallbackGap={row.range?.status === "none"} />
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-body-sm font-extrabold print:hidden">
        <Link href={`/${section.kind}`} className="inline-flex min-h-[44px] items-center text-bubbles-sky-deep underline">
          {rows.length > shown.length ? `See all ${rows.length}` : section.add}
        </Link>
        {rows.length > shown.length && (
          <Link href={`/${section.kind}`} className="inline-flex min-h-[44px] items-center text-muted underline">
            {section.add}
          </Link>
        )}
      </p>
    </section>
  );
}
