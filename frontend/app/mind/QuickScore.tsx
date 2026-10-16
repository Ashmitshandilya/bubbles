"use client";

// One-tap quick scores (loneliness 1 to 5, anxiety 0 to 10). Tapping a number saves it as a score only and shows the server's kind answer.
// No mascot, no colour-coded severity, no label for the person.

import { useState } from "react";
import { ErrorNotice, LiveRegion, Notice } from "../../components/wellness/ui";
import { useWellnessSend } from "../../components/wellness/useWellness";
import type { ScreenResult } from "../../app/lib/wellness-types";
import { QUICK, type QuickKind } from "./hub";

export function QuickScore({ kind, onSaved, children }: { kind: QuickKind; onSaved: () => void; children?: (result: ScreenResult) => React.ReactNode }) {
  const send = useWellnessSend();
  const spec = QUICK[kind];
  const [picked, setPicked] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ScreenResult | null>(null);

  async function choose(value: number) {
    setPicked(value);
    setBusy(true);
    setError("");
    const r = await send<ScreenResult>("/wellness/mind/screen", "POST", { kind, answers: [value] });
    setBusy(false);
    if (!r.ok) return setError(`${r.message} Tap a number to try again.`);
    setResult(r.data);
    onSaved();
  }

  const wide = spec.options.length > 5;
  return (
    <div className="flex flex-col gap-3">
      <fieldset className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
        <legend className="mb-2 p-0 text-body font-extrabold">{spec.question}</legend>
        <div className={wide ? "grid grid-cols-6 gap-2 sm:grid-cols-11" : "grid grid-cols-2 gap-2 sm:grid-cols-5"}>
          {spec.options.map((o) => (
            <button
              key={o.value}
              type="button"
              disabled={busy}
              aria-pressed={picked === o.value}
              onClick={() => void choose(o.value)}
              className={`bubbles-press flex min-h-[48px] flex-col items-center justify-center rounded-2xl border px-2 py-1 text-body-sm font-extrabold ${picked === o.value ? "border-bubbles-sun-deep bg-tint-sun text-ink" : "border-line bg-surface text-ink-soft hover:border-line-strong"}`}
            >
              <span>{wide ? o.value : o.label}</span>
              {wide && o.label && <span className="text-[0.6875rem] font-semibold text-muted">{o.label}</span>}
            </button>
          ))}
        </div>
      </fieldset>
      {error && <ErrorNotice message={error} />}
      {result && (
        <>
          <LiveRegion message={result.message} />
          <Notice tone="soft" title="Thank you for checking in">
            <p className="m-0 whitespace-pre-line">{result.message}</p>
          </Notice>
          {children?.(result)}
        </>
      )}
    </div>
  );
}
