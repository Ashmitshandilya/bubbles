"use client";

// Today's doses (Taken / Snooze / Skip), plus the interaction and allergy panel. Bubbles only records what the person tells it:
// it never suggests, changes or calculates a dose, and every warning points to the pharmacist or prescriber.

import { useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, PILL } from "../../components/hub/HubKit";
import { Choices, TextField } from "../../components/tracking/kit";
import { BTN_TEXT, EmptyNote, ErrorNotice, LiveRegion, Notice, Panel, SelectField } from "../../components/wellness/ui";
import { useWellnessSend } from "../../components/wellness/useWellness";
import { SITE_LABELS, SKIP_REASON_LABELS, STATUS_WORDS, byDoseUrgency } from "../../app/lib/wellness-meds";
import { plural } from "../../app/lib/wellness-format";
import type { AllergyWarning, DueItem, DoseStatus, Glp1Overview, Interaction, MedsToday, Warnings } from "../../app/lib/wellness-types";

const STATUS_STYLE: Record<DoseStatus, string> = {
  upcoming: "bg-blush text-ink-soft",
  due: "bg-tint-sun text-bubbles-sun-deep",
  late: "bg-tint-peach text-bubbles-peach-deep",
  taken: "bg-tint-mint text-bubbles-mint-deep",
  skipped: "bg-tint-grape text-bubbles-grape-deep",
  snoozed: "bg-tint-sky text-bubbles-sky-deep",
};
const STATUS_MARK: Record<DoseStatus, string> = { upcoming: "○", due: "●", late: "◔", taken: "✓", skipped: "–", snoozed: "⏸" };

type Mode = null | "skip" | "snooze" | "site";

export function DueList({ today, glp1, onChanged, onAdd }: { today: MedsToday; glp1: Glp1Overview | null; onChanged: () => void; onAdd: () => void }) {
  const [said, setSaid] = useState("");
  const items = [...today.items].sort(byDoseUrgency);
  const nothing = items.length === 0 && today.as_needed.length === 0 && today.pill_free.length === 0;
  const c = today.counts;
  const summary = [c.late && `${c.late} not recorded yet`, c.due && `${c.due} due now`, c.upcoming && `${c.upcoming} coming up`, c.taken && `${c.taken} taken`, c.skipped && `${c.skipped} skipped`, c.snoozed && `${c.snoozed} snoozed`].filter(Boolean).join(" · ");

  return (
    <Panel title="Today" kicker={new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}>
      {nothing ? (
        <EmptyNote title="Nothing scheduled today" action={<button type="button" onClick={onAdd} className={BTN_PRIMARY}>Add a medicine schedule</button>}>
          Add what you take, with times, and Bubbles will list each dose here so you can tick it off. Bubbles only records what you tell it.
        </EmptyNote>
      ) : (
        <>
          {summary && <p className="m-0 text-body-sm font-bold text-ink-soft">{summary}</p>}
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {items.map((item) => (
              <DoseRow key={`${item.schedule_id}-${item.time}`} item={item} today={today} suggestedSite={glp1?.schedule?.schedule_id === item.schedule_id ? glp1.schedule.suggested_site : undefined} onChanged={onChanged} onSaid={setSaid} />
            ))}
          </ul>
        </>
      )}

      {today.pill_free.map((p) => (
        <Notice key={p.schedule_id} tone="calm" title={p.name}>
          {p.message}
        </Notice>
      ))}

      {today.as_needed.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="m-0 font-display text-h4 text-default">When needed</h3>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {today.as_needed.map((a) => (
              <AsNeededRow key={a.schedule_id} item={a} onChanged={onChanged} onSaid={setSaid} />
            ))}
          </ul>
        </div>
      )}

      {today.refill_alerts.map((r) => (
        <Notice key={r.schedule_id} tone="warm" title={`${r.name}: a good time to ask for a refill`}>
          {r.message ?? `About ${r.pills_left} left on your count.`}
        </Notice>
      ))}

      <details className="rounded-2xl bg-blush px-4 py-3 text-body-sm text-muted">
        <summary className="cursor-pointer font-extrabold text-ink">What if I miss a dose?</summary>
        <p className="m-0 mt-2">{today.missed_dose_help}</p>
      </details>
      <LiveRegion message={said} />
    </Panel>
  );
}

function DoseRow({ item, today, suggestedSite, onChanged, onSaid }: { item: DueItem; today: MedsToday; suggestedSite?: string; onChanged: () => void; onSaid: (m: string) => void }) {
  const send = useWellnessSend();
  const [mode, setMode] = useState<Mode>(null);
  const [changing, setChanging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reason, setReason] = useState("forgot");
  const [site, setSite] = useState(suggestedSite ?? "abdomen_left");
  const finished = (item.status === "taken" || item.status === "skipped") && !changing;
  const isInjection = item.kind === "glp1";

  async function record(status: "taken" | "skipped" | "snoozed", extra: Record<string, unknown> = {}) {
    setBusy(true);
    setError("");
    const result = await send<{ record: { status: string; message?: string } }>("/wellness/meds/dose", "POST", { schedule_id: item.schedule_id, time: item.time, status, ...extra });
    setBusy(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    const verb = status === "taken" ? "Marked as taken" : status === "skipped" ? "Skipped" : "Snoozed";
    onSaid(`${verb}: ${item.name} at ${item.time}. ${result.data.record.message ?? ""}`.trim());
    setMode(null);
    setChanging(false);
    onChanged();
  }

  return (
    <li className="rounded-2xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="font-display text-h3 text-default">{item.time}</span>
          <div className="min-w-0">
            <p className="m-0 break-words font-display text-h4 text-default">{item.name}</p>
            {item.dose_label && <p className="m-0 text-body-sm text-muted">{item.dose_label}</p>}
            {item.placebo && <p className="m-0 text-body-sm text-muted">Reminder pill in your pack (no active medicine).</p>}
          </div>
        </div>
        <span className={`${PILL} ${STATUS_STYLE[item.status]}`}>
          <span aria-hidden="true">{STATUS_MARK[item.status]}</span>
          {STATUS_WORDS[item.status]}
          {item.status === "snoozed" && item.snoozed_until ? ` until ${item.snoozed_until}` : ""}
        </span>
      </div>

      {item.status === "late" && item.message && <p className="m-0 mt-3 rounded-2xl bg-blush px-4 py-3 text-body-sm text-ink">{item.message}</p>}

      {finished ? (
        <div className="mt-3">
          <button type="button" onClick={() => setChanging(true)} className={BTN_TEXT}>
            Change this
          </button>
        </div>
      ) : mode === null ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" disabled={busy} onClick={() => (isInjection ? setMode("site") : void record("taken"))} className={BTN_PRIMARY}>
            Taken
          </button>
          <button type="button" disabled={busy} onClick={() => setMode("snooze")} className={BTN_SECONDARY}>
            Snooze
          </button>
          <button type="button" disabled={busy} onClick={() => setMode("skip")} className={BTN_SECONDARY}>
            Skip
          </button>
          {changing && (
            <button type="button" onClick={() => setChanging(false)} className={BTN_TEXT}>
              Cancel
            </button>
          )}
        </div>
      ) : mode === "snooze" ? (
        <div className="mt-3 flex flex-col gap-2" role="group" aria-label={`Snooze ${item.name}`}>
          <p className="m-0 text-body-sm font-bold text-ink">Remind me again in…</p>
          <div className="flex flex-wrap gap-2">
            {today.snooze_options.map((m) => (
              <button key={m} type="button" disabled={busy} onClick={() => void record("snoozed", { snooze_minutes: m })} className={BTN_SECONDARY}>
                {m} min
              </button>
            ))}
            <button type="button" onClick={() => setMode(null)} className={BTN_TEXT}>
              Back
            </button>
          </div>
        </div>
      ) : mode === "skip" ? (
        <div className="mt-3 flex flex-col gap-3" role="group" aria-label={`Skip ${item.name}`}>
          <SelectField id={`skip-${item.schedule_id}-${item.time}`} label="Skipping because…" value={reason} onChange={setReason} options={today.skip_reasons.map((r) => ({ value: r, label: SKIP_REASON_LABELS[r] ?? r }))} hint="This is just for your record. There's no judgement." />
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={busy} onClick={() => void record("skipped", { reason })} className={BTN_PRIMARY}>
              Skip this dose
            </button>
            <button type="button" onClick={() => setMode(null)} className={BTN_TEXT}>
              Back
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-col gap-3" role="group" aria-label={`Where did you inject ${item.name}`}>
          <Choices id={`site-${item.schedule_id}`} legend="Where did you inject?" hint="Rotating the spot each time is usually suggested. Follow the instructions you were given." options={Object.entries(SITE_LABELS).map(([value, label]) => ({ value, label }))} value={site} onChange={(v) => v && setSite(v)} signal="sky" allowDeselect={false} />
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={busy} onClick={() => void record("taken", { site })} className={BTN_PRIMARY}>
              Mark as taken
            </button>
            <button type="button" disabled={busy} onClick={() => void record("taken")} className={BTN_SECONDARY}>
              Taken, skip the spot
            </button>
            <button type="button" onClick={() => setMode(null)} className={BTN_TEXT}>
              Back
            </button>
          </div>
        </div>
      )}
      {error && <div className="mt-3"><ErrorNotice message={error} /></div>}
    </li>
  );
}

function AsNeededRow({ item, onChanged, onSaid }: { item: MedsToday["as_needed"][number]; onChanged: () => void; onSaid: (m: string) => void }) {
  const send = useWellnessSend();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function take() {
    setBusy(true);
    setError("");
    const result = await send("/wellness/meds/dose", "POST", { schedule_id: item.schedule_id, status: "taken" });
    setBusy(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    onSaid(`Recorded a dose of ${item.name}.`);
    onChanged();
  }
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface p-4">
      <div className="min-w-0">
        <p className="m-0 font-display text-h4 text-default">{item.name}</p>
        <p className="m-0 text-body-sm text-muted">
          {item.dose_label ? `${item.dose_label} · ` : ""}
          {item.taken_today === 0 ? "Not taken today" : `Recorded ${plural(item.taken_today, "time")} today`}
        </p>
        {error && <ErrorNotice message={error} />}
      </div>
      <button type="button" disabled={busy} onClick={() => void take()} className={BTN_SECONDARY}>
        {busy ? "Saving…" : "I took one"}
      </button>
    </li>
  );
}

/* ── Interactions and allergies ─────────────────────────────────────── */

const LEVEL_WORDS: Record<Interaction["level"], string> = {
  high: "Worth a careful check",
  moderate: "Worth checking",
  timing: "A timing tip",
};
const LEVEL_STYLE: Record<Interaction["level"], string> = {
  high: "bg-tint-peach text-bubbles-peach-deep",
  moderate: "bg-tint-sun text-bubbles-sun-deep",
  timing: "bg-tint-sky text-bubbles-sky-deep",
};
const PHARMACIST_LINE = "Please check with your pharmacist or prescriber. This is a short, curated list, not a complete one, and it never tells you to stop or change a medicine.";

function WarningList({ interactions, allergies }: { interactions: Interaction[]; allergies: AllergyWarning[] }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-3 p-0">
      {allergies.map((a) => (
        <li key={`${a.medicine}-${a.allergen}`} className="rounded-2xl bg-tint-peach px-4 py-3">
          <p className="m-0"><span className={`${PILL} bg-surface text-bubbles-peach-deep`}>Allergy note</span></p>
          <p className="m-0 mt-2 text-body-sm font-bold text-ink">{a.message}</p>
        </li>
      ))}
      {interactions.map((i) => (
        <li key={`${i.rule}-${i.names.join("+")}`} className="rounded-2xl bg-blush px-4 py-3">
          <p className="m-0"><span className={`${PILL} ${LEVEL_STYLE[i.level]}`}>{LEVEL_WORDS[i.level]}</span></p>
          <p className="m-0 mt-2 text-body-sm font-bold text-ink">{i.message}</p>
        </li>
      ))}
    </ul>
  );
}

export function WarningsPanel({ warnings }: { warnings: Warnings }) {
  const send = useWellnessSend();
  const [name, setName] = useState("");
  const [names, setNames] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ checked: string[]; interactions: Interaction[]; allergy_warnings: AllergyWarning[]; note: string; lookup: string } | null>(null);
  const [said, setSaid] = useState("");
  const any = warnings.interactions.length + warnings.allergy_warnings.length > 0;

  function addName() {
    const v = name.trim();
    if (!v) return;
    if (!names.some((n) => n.toLowerCase() === v.toLowerCase())) setNames((cur) => [...cur, v].slice(0, 10));
    setName("");
  }

  async function check() {
    const list = name.trim() ? [...names, name.trim()] : names;
    if (list.length === 0) {
      setError("Add a medicine to check first.");
      return;
    }
    setNames(list);
    setName("");
    setBusy(true);
    setError("");
    const r = await send<NonNullable<typeof result>>("/wellness/meds/interactions", "POST", { names: list, include_my_medicines: true }, { tz: false });
    setBusy(false);
    if (!r.ok) {
      setError(r.message);
      return;
    }
    setResult(r.data);
    const n = r.data.interactions.length + r.data.allergy_warnings.length;
    setSaid(n === 0 ? "Nothing found on Bubbles' short list." : `${plural(n, "thing")} to check with your pharmacist.`);
  }

  return (
    <Panel title="Worth checking with your pharmacist" kicker="Interactions and allergies">
      {any ? (
        <WarningList interactions={warnings.interactions} allergies={warnings.allergy_warnings} />
      ) : (
        <p className="m-0 text-body-sm text-muted">Nothing flagged among the medicines you&apos;ve added, using Bubbles&apos; short list and the allergies you&apos;ve recorded.</p>
      )}
      <Notice tone="info">{PHARMACIST_LINE}</Notice>

      <div className="flex flex-col gap-3 rounded-2xl border border-dashed border-line-strong p-4">
        <h3 className="m-0 font-display text-h4 text-default">Thinking of adding something?</h3>
        <TextField id="check-name" label="A medicine or supplement to check" value={name} onChange={setName} placeholder="For example ibuprofen" maxLength={100} hint="Bubbles will check it against your own medicines and your recorded allergies." />
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={addName} className={BTN_SECONDARY}>
            Add to list
          </button>
          <button type="button" disabled={busy} onClick={() => void check()} className={BTN_PRIMARY}>
            {busy ? "Checking…" : "Check"}
          </button>
        </div>
        {names.length > 0 && (
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0" aria-label="Medicines to check">
            {names.map((n) => (
              <li key={n}>
                <button type="button" onClick={() => setNames((cur) => cur.filter((x) => x !== n))} aria-label={`Remove ${n} from the list`} className="bubbles-press min-h-[44px] rounded-full bg-tint-sky px-4 text-body-sm font-extrabold text-bubbles-sky-deep">
                  {n} ✕
                </button>
              </li>
            ))}
          </ul>
        )}
        {error && <ErrorNotice message={error} />}
        <LiveRegion message={said} />
        {result && (
          <div className="flex flex-col gap-3">
            {result.interactions.length + result.allergy_warnings.length === 0 ? (
              <Notice tone="calm" title="Nothing found on Bubbles' short list">
                That isn&apos;t a clearance. {result.note}
              </Notice>
            ) : (
              <>
                <WarningList interactions={result.interactions} allergies={result.allergy_warnings} />
                <p className="m-0 text-body-sm text-muted">{result.note}</p>
              </>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
