"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "../../../components/Providers";
import { BTN_SECONDARY, ErrorCard, HubPage, Skeleton } from "../../../components/hub/HubKit";
import { actionBody, joinWords, readUnderstanding, type Understanding } from "./understanding";

export function UnderstandingClient() {
  return (
    <HubPage title="How Bubbles understands you">
      <Understood />
    </HubPage>
  );
}

function Understood() {
  const { fetchBubbles } = useApi();
  const [data, setData] = useState<Understanding | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const response = await fetchBubbles("/me/understanding");
      const next = response.ok ? readUnderstanding(await response.json()) : null;
      if (next) setData(next);
      else setFailed(true);
    } catch {
      setFailed(true);
    }
  }, [fetchBubbles]);

  useEffect(() => {
    void load();
  }, [load]);

  async function send(id: string, action: "confirm" | "reject") {
    setBusy(id);
    setProblem(null);
    try {
      const response = await fetchBubbles(`/me/understanding/${id}`, { method: "PUT", body: actionBody(action) });
      const next = response.ok ? readUnderstanding(await response.json()) : null;
      if (!next) throw new Error("understanding");
      setData(next);
    } catch {
      setProblem("That did not save. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  async function clearAll() {
    setBusy("all");
    setProblem(null);
    try {
      const response = await fetchBubbles("/me/understanding", { method: "DELETE" });
      const next = response.ok ? readUnderstanding(await response.json()) : null;
      if (!next) throw new Error("understanding");
      setData(next);
      setClearing(false);
    } catch {
      setProblem("That did not clear. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  if (failed) return <ErrorCard title="This did not load" message="Check your connection and try again." onRetry={() => void load()} />;
  if (!data) return <Skeleton className="h-40 w-full" />;

  return (
    <div className="mx-auto max-w-2xl">
      <p className="m-0 text-body text-muted">
        What Bubbles has noticed about how you like to be talked to. It is only ever used to choose words, and you can correct any line.
      </p>

      {data.traits.length === 0 ? (
        <div className="mt-8">
          <p className="m-0 text-h4 text-ink">{data.intro}</p>
          {data.wouldUse.length > 0 && <p className="mt-2 text-body text-muted">As you chat, it will pick up {joinWords(data.wouldUse)}.</p>}
        </div>
      ) : (
        <ul className="m-0 mt-6 list-none p-0">
          {data.traits.map((t) => (
            <li key={t.id} className="border-t border-line py-5 first:border-t-0">
              <p className="m-0 text-h4 text-ink">{t.line}</p>
              <p className="mt-1 text-body-sm text-muted">
                {t.confidence}.{t.why ? ` ${t.why}` : ""}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {t.state === "confirmed" ? (
                  <span className="inline-flex items-center text-body-sm font-extrabold text-ink">You said this is right</span>
                ) : (
                  <button type="button" className={BTN_SECONDARY} disabled={busy !== null} onClick={() => void send(t.id, "confirm")}>
                    That&apos;s me
                  </button>
                )}
                <button type="button" className={BTN_SECONDARY} disabled={busy !== null} onClick={() => void send(t.id, "reject")}>
                  Not me
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {problem && (
        <p role="alert" className="mt-4 text-body-sm font-bold text-bubbles-urgent">
          {problem}
        </p>
      )}

      <div className="mt-10 border-t border-line pt-5">
        {clearing ? (
          <div className="flex flex-wrap items-center gap-2">
            <p className="m-0 text-body-sm text-ink">Clear everything Bubbles has learned, including the lines you said were not you?</p>
            <button type="button" className={BTN_SECONDARY} disabled={busy !== null} onClick={() => void clearAll()}>
              Yes, clear it
            </button>
            <button type="button" className={BTN_SECONDARY} disabled={busy !== null} onClick={() => setClearing(false)}>
              Keep it
            </button>
          </div>
        ) : (
          <button type="button" className={BTN_SECONDARY} disabled={busy !== null} onClick={() => setClearing(true)}>
            Start fresh
          </button>
        )}
      </div>
    </div>
  );
}
