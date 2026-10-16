"use client";

import { useCallback, useEffect, useId, useState } from "react";
import Link from "next/link";
import { useApi } from "../../components/Providers";
import { CARD, ErrorCard, HubPage, Skeleton } from "../../components/hub/HubKit";
import {
  changeBody,
  historyLine,
  readHistory,
  readOverview,
  readPurpose,
  withPurpose,
  type ConsentHistoryItem,
  type ConsentOverview,
  type ConsentPurpose,
} from "../lib/consents";

export function PrivacyChoicesClient() {
  return (
    <HubPage title="Privacy choices">
      <PrivacyChoices />
    </HubPage>
  );
}

function PrivacyChoices() {
  const { fetchBubbles } = useApi();
  const [overview, setOverview] = useState<ConsentOverview | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [history, setHistory] = useState<ConsentHistoryItem[] | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const response = await fetchBubbles("/consents");
      const next = response.ok ? readOverview(await response.json()) : null;
      if (next) setOverview(next);
      else setFailed(true);
    } catch {
      setFailed(true);
    }
  }, [fetchBubbles]);

  const loadHistory = useCallback(async () => {
    try {
      const response = await fetchBubbles("/consents/history?limit=100");
      setHistory(response.ok ? readHistory(await response.json()) : []);
    } catch {
      setHistory([]);
    }
  }, [fetchBubbles]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (historyOpen && history === null) void loadHistory();
  }, [historyOpen, history, loadHistory]);

  async function change(purpose: ConsentPurpose, granted: boolean) {
    setBusy(purpose.id);
    setProblem(null);
    try {
      const response = await fetchBubbles(`/consents/${purpose.id}`, { method: "PUT", body: changeBody(purpose, granted, "settings") });
      if (response.status === 409) {
        // The wording changed since this page loaded: show the new wording, do not guess.
        await load();
        setProblem("The wording of that choice just changed. Please read it and try again.");
        return;
      }
      const next = response.ok ? readPurpose(((await response.json()) as { consent?: unknown })?.consent) : null;
      if (!next) throw new Error("consent");
      setOverview((current) => (current ? { ...current, purposes: withPurpose(current.purposes, next) } : current));
      if (historyOpen) void loadHistory();
      else setHistory(null);
    } catch {
      setProblem("Bubbles couldn't save that just now. Nothing changed. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="bubbles-rise text-h1 text-ink">Privacy choices</h1>
      <p className="m-0 text-body text-ink-soft">Each choice is off until you turn it on. Turn any of them off again at any time.</p>

      {!overview && !failed && (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      )}
      {failed && !overview && <ErrorCard title="Couldn't load your choices" message="Check your connection and try again." onRetry={() => void load()} />}

      {overview && (
        <>
          <ul className={`${CARD} m-0 list-none divide-y-2 divide-line overflow-hidden p-0`}>
            {overview.purposes.map((p) => (
              <ChoiceRow key={p.id} purpose={p} busy={busy === p.id} onChange={(granted) => void change(p, granted)} />
            ))}
          </ul>

          <p role="status" aria-live="polite" className={problem ? "m-0 rounded-2xl bg-tint-peach px-4 py-3 text-body-sm font-bold text-bubbles-peach-deep" : "sr-only"}>
            {problem ?? ""}
          </p>

          {overview.disclosures.map((d) => (
            <section key={d.id} className={`${CARD} px-5 py-4`}>
              <h2 className="m-0 font-display text-lg font-semibold text-ink">{d.title}</h2>
              <p className="m-0 mt-1 text-body-sm text-muted">{d.text}</p>
            </section>
          ))}

          <details
            className="group rounded-[24px] border border-line bg-surface shadow-sm"
            onToggle={(event) => setHistoryOpen((event.currentTarget as HTMLDetailsElement).open)}
          >
            <summary className="flex min-h-[56px] cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 font-display text-lg font-semibold text-ink [&::-webkit-details-marker]:hidden">
              What you agreed to
              <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-90">&rsaquo;</span>
            </summary>
            <div className="px-5 pb-4">
              {history === null ? (
                <Skeleton className="h-10" />
              ) : history.length === 0 ? (
                <p className="m-0 text-body-sm text-muted">Nothing yet. Each time you turn a choice on or off, it is listed here.</p>
              ) : (
                <ol className="m-0 list-none space-y-3 p-0">
                  {history.map((item, i) => (
                    <li key={`${item.createdAt}-${item.purpose}-${i}`}>
                      <p className="m-0 text-body-sm font-bold text-ink">{item.title}</p>
                      <p className="m-0 text-body-sm text-muted">{historyLine(item)}</p>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </details>

          <p className="m-0 text-body-sm text-muted">
            <Link href="/privacy" className="inline-flex min-h-[44px] items-center font-extrabold text-bubbles-pink-ink underline">
              Read the privacy notice
            </Link>
            {overview.policyVersion ? <span className="ml-2">Version {overview.policyVersion}</span> : null}
          </p>
        </>
      )}
    </div>
  );
}

function ChoiceRow({ purpose, busy, onChange }: { purpose: ConsentPurpose; busy: boolean; onChange: (granted: boolean) => void }) {
  const labelId = useId();
  const hintId = useId();
  const on = purpose.granted;
  return (
    <li className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-4">
      <div className="min-w-0 max-w-[30rem]">
        <p id={labelId} className="m-0 font-bold text-ink">
          {purpose.title}
        </p>
        <p id={hintId} className="m-0 mt-1 text-body-sm text-muted">
          {purpose.description}
        </p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-labelledby={labelId}
        aria-describedby={hintId}
        disabled={busy || !purpose.available}
        onClick={() => onChange(!on)}
        className="bubbles-press inline-flex min-h-[44px] min-w-[64px] shrink-0 items-center justify-center rounded-full disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span
          aria-hidden="true"
          className={`relative inline-flex h-8 w-14 items-center rounded-full border transition-colors ${on ? "border-bubbles-grape bg-bubbles-grape" : "border-line-strong bg-surface"}`}
        >
          <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${on ? "translate-x-7" : "translate-x-1 !bg-line-strong"}`} />
        </span>
      </button>
    </li>
  );
}
