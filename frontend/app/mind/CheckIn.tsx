"use client";

// One-tap-style mood check-in: pick a face, optionally tick what you did, optionally add a note, save.
// If the note contains urgent or crisis wording, the server answers with the safety message instead of saving.
// That message is shown first, with no mascot and no cheer. A rough day gets a calm, plain answer (also no mascot).

import { useState } from "react";
import { BTN_PRIMARY } from "../../components/hub/HubKit";
import { SavedToast, TextArea } from "../../components/tracking/kit";
import { ErrorNotice, LiveRegion, Notice, Panel, SafetyCard, ToggleChips } from "../../components/wellness/ui";
import { useWellnessSend } from "../../components/wellness/useWellness";
import { humanizeKey, plural } from "../../app/lib/wellness-format";
import { isSafety, type MindOverview, type SafetyResponse } from "../../app/lib/wellness-types";

const FACE_MOUTH: Record<number, string> = {
  1: "M9 20 Q16 13 23 20",
  2: "M10 20 Q16 16.5 22 20",
  3: "M10 19 L22 19",
  4: "M10 18 Q16 22.5 22 18",
  5: "M9 17.5 Q16 25 23 17.5",
};
const FACE_FILL: Record<number, string> = { 1: "#FFC9AE", 2: "#FCE8A9", 3: "#DDF7EE", 4: "#A9E8D2", 5: "#22C39A" };

function Face({ n }: { n: number }) {
  return (
    <svg width="44" height="44" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <circle cx="16" cy="16" r="14" fill={FACE_FILL[n]} stroke="#2B1A3F" strokeWidth="1.8" />
      <circle cx="11.5" cy="12.5" r="1.7" fill="#2B1A3F" />
      <circle cx="20.5" cy="12.5" r="1.7" fill="#2B1A3F" />
      <path d={FACE_MOUTH[n]} fill="none" stroke="#2B1A3F" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function CheckIn({ overview, onSaved }: { overview: MindOverview; onSaved: () => void }) {
  const send = useWellnessSend();
  const [face, setFace] = useState<number | null>(null);
  const [acts, setActs] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [support, setSupport] = useState("");
  const [safety, setSafety] = useState<SafetyResponse | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  async function save() {
    if (face === null) {
      setError("Pick the face that fits best first.");
      return;
    }
    setBusy(true);
    setError("");
    const body: Record<string, unknown> = { face, activities: acts };
    if (notes.trim()) body.notes = notes.trim();
    const result = await send<{ level: number; support?: string } | SafetyResponse>("/wellness/mind/checkin", "POST", body);
    setBusy(false);
    if (!result.ok) {
      setError(`${result.message} Your check-in is still here.`);
      return;
    }
    if (isSafety(result.data)) {
      setSafety(result.data);
      setMessage("");
      setSupport("");
      return;
    }
    const d = result.data as { level: number; support?: string };
    setSafety(null);
    setMessage("Check-in saved.");
    setSupport(d.support ?? "");
    if (!d.support) setSavedAt(`${Date.now()}`); // the happy toast (with the mascot) is only for ordinary good-enough days
    setFace(null);
    setActs([]);
    setNotes("");
    onSaved();
  }

  const today = overview.today;
  return (
    <>
      {safety && <SafetyCard response={safety} onClose={() => setSafety(null)} />}
      <Panel id="checkin" title="How are you feeling right now?" kicker={today ? `Checked in ${plural(today.n, "time")} today` : "Your check-in"}>
        <fieldset className="m-0 border-0 p-0">
          <legend className="sr-only">Choose the face that fits best</legend>
          <div className="grid grid-cols-5 gap-2">
            {overview.faces.map((f) => {
              const on = face === f.face;
              return (
                <button
                  key={f.face}
                  type="button"
                  aria-pressed={on}
                  onClick={() => {
                    setFace(f.face);
                    setError("");
                  }}
                  className={`bubbles-press flex min-h-[84px] flex-col items-center justify-center gap-1 rounded-2xl border-2 px-1 py-2 text-body-sm font-extrabold ${on ? "border-bubbles-sun-deep bg-tint-sun text-ink" : "border-line bg-surface text-ink-soft hover:border-line-strong"}`}
                >
                  <Face n={f.face} />
                  {f.label}
                </button>
              );
            })}
          </div>
        </fieldset>

        <ToggleChips
          legend="What have you been up to?"
          options={overview.activities.map((a) => ({ value: a, label: humanizeKey(a) }))}
          selected={acts}
          onToggle={(a) => setActs((cur) => (cur.includes(a) ? cur.filter((x) => x !== a) : [...cur, a]))}
          signal="sun"
          optional
        />
        <TextArea id="checkin-notes" label="Anything to add?" value={notes} onChange={setNotes} maxLength={1000} placeholder="Just for you. A few words are plenty." optional />

        {error && <ErrorNotice message={error} />}
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" disabled={busy} onClick={() => void save()} className={BTN_PRIMARY}>
            {busy ? "Saving…" : "Save check-in"}
          </button>
        </div>
        <LiveRegion message={message + (support ? ` ${support}` : "")} />
        {message && !support && <p className="m-0 text-body-sm font-extrabold text-bubbles-mint-deep">{message}</p>}
        {support && (
          <Notice tone="soft" title="Check-in saved">
            <p className="m-0">{support}</p>
          </Notice>
        )}
        <p className="m-0 text-body-sm text-muted">{overview.note}</p>
      </Panel>
      <SavedToast trigger={savedAt} message="Check-in saved!" />
    </>
  );
}
