"use client";

// The Playbook tab: reply shapes that 20 or more people found helpful, drafted automatically, approved or retired by the owner here.
// Nothing reaches a user until it is approved. Only counts of people are shown, never who they are.

import { useState } from "react";
import { BTN_SECONDARY } from "../../components/hub/HubKit";
import { responseFailure } from "../../lib/api";
import { humanize } from "./format";
import { Empty, LoadState, Panel, Pill, useAdmin, useAdminQuery } from "./kit";

type Entry = {
  id: string; intent: string; language: string; status: "draft" | "approved" | "retired"; guidance_text: string; example_text: string;
  uses: number; helpful: number; people: number; flagged: boolean;
};
type Listing = { ready: boolean; entries: Entry[]; message?: string; min_people?: number };

const ACT = "bubbles-press min-h-[44px] rounded-full border px-4 text-body-sm font-extrabold";

function EntryRow({ entry, onDone }: { entry: Entry; onDone: () => void }) {
  const { adminFetch } = useAdmin();
  const [text, setText] = useState(entry.guidance_text || entry.example_text);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const send = async (action: "approve" | "retire" | "edit") => {
    setBusy(true);
    setError("");
    try {
      const res = await adminFetch(`/admin/playbook/${encodeURIComponent(entry.id)}`, { method: "POST", body: JSON.stringify({ action, guidance_text: action === "retire" ? undefined : text }) });
      if (!res.ok) setError((await responseFailure(res)).message);
      else onDone();
    } finally {
      setBusy(false);
    }
  };
  const tone = entry.status === "approved" ? "mint" : entry.status === "draft" ? "sun" : "plain";
  return (
    <li className="flex flex-col gap-2 border-b border-[color:var(--hairline)] pb-4">
      <div className="flex flex-wrap items-center gap-2 text-body-sm">
        <Pill tone={tone}>{humanize(entry.status)}</Pill>
        <strong>{humanize(entry.intent)}</strong>
        <span className="text-muted">{entry.language}</span>
        <span className="text-muted">{entry.people} people</span>
        {entry.status === "approved" && <span className="text-muted">used {entry.uses}, helpful {entry.helpful}</span>}
        {entry.flagged && <Pill tone="urgent">Stopped helping: look again</Pill>}
      </div>
      <label className="text-label text-ink-soft" htmlFor={`pb-${entry.id}`}>What Bubbles is shown (edit before approving)</label>
      <textarea id={`pb-${entry.id}`} className="pearl-field" rows={3} maxLength={700} value={text} onChange={(e) => setText(e.target.value)} disabled={entry.status === "retired"} />
      {error && <p role="alert" className="m-0 text-body-sm font-bold text-bubbles-urgent">{error}</p>}
      <div className="flex flex-wrap gap-2">
        {entry.status !== "retired" && <button type="button" disabled={busy || !text.trim()} onClick={() => void send("approve")} className={`${ACT} border-bubbles-pink-ink bg-bubbles-pink-ink text-white`}>{entry.status === "approved" ? "Save edit" : "Approve"}</button>}
        {entry.status !== "retired" && <button type="button" disabled={busy} onClick={() => void send("retire")} className={`${ACT} border-line-strong bg-surface`}>Retire</button>}
      </div>
    </li>
  );
}

export function PlaybookPanel() {
  const [state, reload] = useAdminQuery<Listing>("/admin/playbook");
  return (
    <Panel title="Playbook" id="playbook" action={<button type="button" className={BTN_SECONDARY} onClick={reload}>Refresh</button>}>
      <p className="m-0 mb-4 text-body-sm text-muted">
        Short replies to simple app questions that at least 20 people, who each agreed to share, found helpful. Names, numbers and dates are removed before anything is kept.
        Only entries you approve are ever used, and never for health, safety or relationship advice.
      </p>
      <LoadState state={state} title="the Playbook" retry={reload}>
        {(d) => !d.ready ? <Empty>{d.message}</Empty> : d.entries.length === 0 ? <Empty>No drafts yet. A draft appears once {d.min_people ?? 20} different people found the same kind of reply helpful.</Empty> : (
          <ul className="m-0 flex list-none flex-col gap-4 p-0">{d.entries.map((e) => <EntryRow key={e.id} entry={e} onDone={reload} />)}</ul>
        )}
      </LoadState>
    </Panel>
  );
}
