"use client";

// Text-only journal. "Keep this private from AI" sets local_only: that entry never reaches any model or AI context.
// Urgent or crisis wording is answered by the safety message and nothing is saved.

import { useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, PILL } from "../../components/hub/HubKit";
import { BTN_TEXT, EmptyNote, ErrorNotice, INPUT, LiveRegion, Panel, QueryView, SafetyCard, Switch } from "../../components/wellness/ui";
import { useWellnessQuery, useWellnessSend } from "../../components/wellness/useWellness";
import { shortDay } from "../../app/lib/wellness-format";
import { isSafety, type JournalEntry, type SafetyResponse } from "../../app/lib/wellness-types";

const MAX = 5000;

export function Journal() {
  const send = useWellnessSend();
  const [list, reload] = useWellnessQuery<{ entries: JournalEntry[] }>("/wellness/mind/journal?limit=30", { tz: false });
  const [text, setText] = useState("");
  const [localOnly, setLocalOnly] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [said, setSaid] = useState("");
  const [safety, setSafety] = useState<SafetyResponse | null>(null);

  async function save() {
    if (!text.trim()) {
      setError("Write something first.");
      return;
    }
    setBusy(true);
    setError("");
    const result = await send<{ note?: string } | SafetyResponse>("/wellness/mind/journal", "POST", { text: text.trim(), local_only: localOnly });
    setBusy(false);
    if (!result.ok) return setError(`${result.message} What you wrote is still here.`);
    if (isSafety(result.data)) {
      setSafety(result.data);
      setSaid("");
      return;
    }
    setSafety(null);
    setText("");
    setSaid((result.data as { note?: string }).note ?? "Saved privately.");
    reload();
  }

  return (
    <Panel id="journal" title="Journal" kicker="Private, text only">
      {safety && <SafetyCard response={safety} onClose={() => setSafety(null)} />}
      <div className="flex flex-col gap-2">
        <label htmlFor="journal-text" className="text-body font-extrabold">
          What&apos;s on your mind?
        </label>
        <textarea
          id="journal-text" rows={6} value={text} maxLength={MAX} onChange={(e) => { setText(e.target.value); setError(""); }}
          aria-describedby="journal-count" className={`${INPUT} resize-y`} placeholder="Write as much or as little as you like."
        />
        <p id="journal-count" className="m-0 text-right text-body-sm text-muted">
          {text.length} / {MAX}
        </p>
      </div>
      <Switch
        label="Keep this private from AI"
        hint={localOnly ? "This entry stays out of any AI features." : "Bubbles' AI features may use this entry to understand you better."}
        checked={localOnly}
        onChange={setLocalOnly}
        offWord="Off"
        onWord="Private"
      />
      {error && <ErrorNotice message={error} />}
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" disabled={busy} onClick={() => void save()} className={BTN_PRIMARY}>
          {busy ? "Saving…" : "Save entry"}
        </button>
      </div>
      <LiveRegion message={said} />
      {said && <p className="m-0 text-body-sm font-extrabold text-bubbles-mint-deep">{said}</p>}

      <QueryView query={list} onRetry={reload} what="your journal">
        {(d) =>
          d.entries.length === 0 ? (
            <EmptyNote title="No entries yet">Your entries will appear here. Only you can see them.</EmptyNote>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-3 p-0" aria-label="Your journal entries">
              {d.entries.map((e) => (
                <Entry key={e.id} entry={e} onDeleted={reload} />
              ))}
            </ul>
          )
        }
      </QueryView>
    </Panel>
  );
}

function Entry({ entry, onDeleted }: { entry: JournalEntry; onDeleted: () => void }) {
  const send = useWellnessSend();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function remove() {
    setBusy(true);
    const result = await send(`/wellness/mind/journal/${entry.id}`, "DELETE", undefined, { tz: false });
    setBusy(false);
    if (!result.ok) return setError(result.message);
    onDeleted();
  }
  return (
    <li className="rounded-2xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="m-0 text-body-sm font-extrabold text-muted">{shortDay(entry.date, true)}</p>
        <span className={`${PILL} ${entry.local_only ? "bg-tint-grape text-bubbles-grape-deep" : "bg-blush text-ink-soft"}`}>{entry.local_only ? "Private from AI" : "AI features may use this"}</span>
      </div>
      <p className="m-0 mt-2 whitespace-pre-wrap break-words text-body text-ink">{entry.text}</p>
      {!confirm ? (
        <button type="button" onClick={() => setConfirm(true)} className={`${BTN_TEXT} mt-1`} aria-label={`Delete the entry from ${shortDay(entry.date)}`}>
          Delete
        </button>
      ) : (
        <div role="group" aria-label="Confirm delete" className="mt-2 flex flex-wrap items-center gap-2 rounded-2xl bg-blush px-4 py-3">
          <p className="m-0 text-body-sm font-bold text-ink">Delete this entry for good?</p>
          <button type="button" disabled={busy} onClick={() => void remove()} className={BTN_PRIMARY}>
            Yes, delete
          </button>
          <button type="button" onClick={() => setConfirm(false)} className={BTN_SECONDARY}>
            Keep it
          </button>
        </div>
      )}
      {error && <div className="mt-2"><ErrorNotice message={error} /></div>}
    </li>
  );
}
