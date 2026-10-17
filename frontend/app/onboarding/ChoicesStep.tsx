"use client";

import type { ConsentPurpose } from "../lib/consents";

/** The purposes the setup offers. Partner sharing and community are asked where they are used, never here. */
export const OFFERED_PURPOSES = ["ai_chat_processing", "health_memory_from_chat", "push_notifications", "email_reminders"] as const;

const BUTTON = "bubbles-press bubbles-glow inline-flex min-h-[56px] items-center justify-center rounded-full bg-bubbles-pink-ink px-8 text-[1.0625rem] font-extrabold text-white disabled:cursor-wait disabled:opacity-70";
const NEUTRAL = "bubbles-press inline-flex min-h-[52px] items-center justify-center rounded-full border border-line bg-surface px-6 font-extrabold text-ink-soft disabled:opacity-70";

/**
 * "Your choices": one separate switch per offered purpose, all off. Nothing here is needed to carry on: "Not now" and "Continue" are
 * always available, and what is left off is recorded as a no (the caller writes the ledger).
 */
export function ChoicesStep({ purposes, on, failed, busy, onToggle, onNotNow, onContinue, onBack }: {
  purposes: ConsentPurpose[] | null;
  on: ReadonlySet<string>;
  failed: boolean;
  busy: boolean;
  onToggle: (id: string) => void;
  onNotNow: () => void;
  onContinue: () => void;
  onBack: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <h2 className="m-0 font-display text-h2 text-ink">Your choices</h2>
      <p className="m-0 text-body text-muted">Everything is off until you turn it on. You can change any of it later in Privacy choices.</p>

      {purposes === null && !failed && <p role="status" className="m-0 text-body-sm font-bold text-muted">Getting your choices…</p>}
      {failed && <p role="status" className="m-0 rounded-2xl bg-blush px-4 py-3 text-body-sm font-bold text-ink-soft">Your choices couldn&apos;t load just now. You can set them any time in Settings, under Privacy choices.</p>}

      {purposes && (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {purposes.map((p) => {
            const checked = on.has(p.id);
            const labelId = `choice-${p.id}`;
            const hintId = `choice-${p.id}-hint`;
            return (
              <li key={p.id} className="flex items-start justify-between gap-3 rounded-2xl border border-line bg-surface p-4">
                <div className="min-w-0 flex-1">
                  <p id={labelId} className="m-0 text-body font-extrabold">{p.title}</p>
                  <p id={hintId} className="m-0 mt-1 text-body-sm text-muted">{p.description}</p>
                </div>
                <button type="button" role="switch" aria-checked={checked} aria-labelledby={labelId} aria-describedby={hintId} disabled={busy} onClick={() => onToggle(p.id)}
                  className="bubbles-press inline-flex min-h-[44px] min-w-[64px] shrink-0 items-center justify-center rounded-full disabled:opacity-60">
                  <span aria-hidden="true" className={`relative inline-flex h-8 w-14 items-center rounded-full border transition-colors ${checked ? "border-bubbles-grape bg-bubbles-grape" : "border-ink-soft bg-surface"}`}>
                    <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-7" : "translate-x-1 !bg-ink-soft"}`} />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
        <button type="button" onClick={onBack} className={NEUTRAL}>Back</button>
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={onNotNow} disabled={busy} className={NEUTRAL}>Not now</button>
          <button type="button" onClick={onContinue} disabled={busy} className={BUTTON}>{busy ? "Saving…" : "Continue"}</button>
        </div>
      </div>
    </div>
  );
}
