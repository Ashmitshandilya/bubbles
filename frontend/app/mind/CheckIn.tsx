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
const FACE_FILL: Record<number, string> = { 1: "#FBCFC6", 2: "#F1E2C2", 3: "#F4EFE8", 4: "#E3D8CA", 5: "#D9CBB8" };

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

function Slider({ id, label, value, onChange }: { id: string; label: string; value: number | null; onChange: (v: number) => void }) {
  const text = value === null ? "Not set" : `${value} of 10`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="flex items-baseline justify-between text-body-sm font-extrabold text-ink">
        {label}
        <span className="font-semibold text-muted">{text}</span>
      </label>
      <input id={id} type="range" min={0} max={10} step={1} value={value ?? 5} onChange={(e) => onChange(Number(e.target.value))} aria-valuetext={text} className="h-11 w-full accent-bubbles-grape" />
    </div>
  );
}

export function CheckIn({ overview, onSaved }: { overview: MindOverview; onSaved: () => void }) {
  const send = useWellnessSend();
  const [face, setFace] = useState<number | null>(null);
  const [acts, setActs] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [stress, setStress] = useState<number | null>(null);
  const [anxiety, setAnxiety] = useState<number | null>(null);
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
    if (stress !== null) body.stress = stress;
    if (anxiety !== null) body.anxiety = anxiety;
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
    setStress(null);
    setAnxiety(null);
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
                  className={`bubbles-press flex min-h-[84px] flex-col items-center justify-center gap-1 rounded-2xl border px-1 py-2 text-body-sm font-extrabold ${on ? "border-bubbles-sun-deep bg-tint-sun text-ink" : "border-line bg-surface text-ink-soft hover:border-line-strong"}`}
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
        <details className="rounded-2xl border border-line px-4 py-2">
          <summary className="flex min-h-[44px] cursor-pointer items-center text-body-sm font-extrabold text-ink-soft">Add stress or anxiety (optional)</summary>
          <div className="flex flex-col gap-4 pb-3 pt-1">
            <Slider id="checkin-stress" label="Stress today" value={stress} onChange={setStress} />
            <Slider id="checkin-anxiety" label="Anxiety today" value={anxiety} onChange={setAnxiety} />
          </div>
        </details>
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
