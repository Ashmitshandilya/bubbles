"use client";

import { useEffect, useId, useState } from "react";
import { useApi } from "../../components/Providers";
import { ErrorCard, HubPage, Skeleton, useBubblesQuery } from "../../components/hub/HubKit";
import { decisionLine, readChoices, readHistory, type Choice } from "./choices";

export function PrivacyChoicesClient() {
  return (
    <HubPage title="Privacy choices">
      <Choices />
    </HubPage>
  );
}

function Choices() {
  const { fetchBubbles } = useApi();
  const [query, reload] = useBubblesQuery<unknown>("/consents");
  const [history, reloadHistory] = useBubblesQuery<unknown>("/consents/history");
  const [items, setItems] = useState<Choice[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    if (query.status === "ready") setItems(readChoices(query.data));
  }, [query]);

  async function change(choice: Choice, granted: boolean) {
    setBusy(choice.purpose);
    setProblem(null);
    try {
      const response = await fetchBubbles(`/consents/${encodeURIComponent(choice.purpose)}`, { method: "PUT", body: JSON.stringify({ granted, source: "settings" }) });
      if (!response.ok) throw new Error(String(response.status));
      reload();
      reloadHistory();
    } catch {
      setProblem("Bubbles couldn't save that just now. Nothing changed. Try again.");
    } finally {
      setBusy(null);
    }
  }

  const log = history.status === "ready" ? readHistory(history.data) : [];

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="bubbles-rise">
        <h1 className="text-h1 text-ink">Privacy choices</h1>
        <p className="mt-1 text-body-sm text-muted">Everything starts off. Turn on only what you want, and turn it off again any time.</p>
      </header>

      {query.status === "loading" && <Skeleton className="h-64 rounded-3xl" />}
      {query.status === "error" && <ErrorCard title="Your choices didn't load" message={query.message} onRetry={reload} />}
      {problem && <p role="alert" className="m-0 rounded-2xl bg-tint-urgent px-4 py-3 text-body-sm font-bold text-bubbles-urgent">{problem}</p>}

      {items && (
        <ul className="m-0 list-none space-y-3 p-0">
          {items.map((choice) => (
            <ChoiceRow key={choice.purpose} choice={choice} busy={busy === choice.purpose} onChange={(granted) => void change(choice, granted)} />
          ))}
        </ul>
      )}

      {log.length > 0 && (
        <details className="group rounded-[24px] border border-line bg-surface shadow-sm">
          <summary className="flex min-h-[56px] cursor-pointer list-none items-center px-5 py-3 font-display text-lg font-semibold text-ink [&::-webkit-details-marker]:hidden">
            What you agreed to, and when
          </summary>
          <ul className="m-0 list-none divide-y-2 divide-line px-5 pb-3">
            {log.slice(0, 30).map((row, i) => (
              <li key={`${row.purpose}-${row.at}-${i}`} className="flex flex-wrap justify-between gap-x-4 py-2.5 text-body-sm">
                <span className="font-bold text-ink">{row.title}: {row.granted ? "turned on" : "turned off"}</span>
                <span className="text-muted">{row.at ? new Date(row.at).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : ""}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function ChoiceRow({ choice, busy, onChange }: { choice: Choice; busy: boolean; onChange: (granted: boolean) => void }) {
  const labelId = useId();
  const hintId = useId();
  const on = choice.granted;
  return (
    <li className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-[24px] border border-line bg-surface px-5 py-4 shadow-sm">
      <div className="min-w-0 max-w-[32rem]">
        <p id={labelId} className="m-0 font-bold text-ink">{choice.title}</p>
        <p id={hintId} className="m-0 mt-1 text-body-sm text-muted">{choice.what}</p>
        <p className="m-0 mt-1 text-chip font-bold text-ink-soft">{decisionLine(choice)}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-labelledby={labelId}
        aria-describedby={hintId}
        disabled={busy || !choice.available}
        onClick={() => onChange(!on)}
        className={`bubbles-press relative inline-flex h-8 w-14 shrink-0 items-center rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
          on ? "border-bubbles-grape bg-bubbles-grape" : "border-line-strong bg-surface"
        }`}
      >
        <span aria-hidden="true" className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${on ? "translate-x-7" : "translate-x-1 !bg-line-strong"}`} />
      </button>
    </li>
  );
}
