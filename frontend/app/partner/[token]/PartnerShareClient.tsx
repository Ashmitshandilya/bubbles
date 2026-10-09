"use client";

// Public page: what a partner sees. No login, no navigation, one anonymous request (no Authorization header, no cookies).
// It deliberately does not use AuthProvider, which redirects visitors without a session to /login.

import { useCallback, useEffect, useState } from "react";
import { BubblesMascot } from "../../../components/BubblesMascot";
import { partnerErrorMessage } from "../../lib/cycle-public";
import { daysLeft, shareEndpoint, type PartnerShareView } from "../../lib/partner-sharing";
import { SectionCard } from "../SectionCard";

type State = { status: "loading" } | { status: "error"; message: string; gone: boolean } | { status: "ready"; data: PartnerShareView };

export function PartnerShareClient({ token }: { token: string }) {
  const [state, setState] = useState<State>({ status: "loading" });

  const load = useCallback(async (signal?: AbortSignal) => {
    setState({ status: "loading" });
    const timer = new AbortController();
    const timeout = window.setTimeout(() => timer.abort(), 15000);
    signal?.addEventListener("abort", () => timer.abort());
    try {
      const response = await fetch(shareEndpoint(token), { cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal: timer.signal });
      if (!response.ok) {
        setState({ status: "error", message: partnerErrorMessage(response.status), gone: response.status === 404 || response.status === 410 });
        return;
      }
      setState({ status: "ready", data: (await response.json()) as PartnerShareView });
    } catch {
      if (!signal?.aborted) setState({ status: "error", message: partnerErrorMessage(null), gone: false });
    } finally {
      window.clearTimeout(timeout);
    }
  }, [token]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-blush px-4 py-10 text-ink">
      <div className="w-full max-w-md rounded-3xl border-2 border-line bg-surface p-6 text-center sm:p-8">
        {state.status === "loading" && (
          <div role="status">
            <BubblesMascot size={80} mood="thinking" className="mx-auto" />
            <p className="mb-0 mt-4 text-body font-bold text-muted">Opening the shared link…</p>
          </div>
        )}

        {state.status === "error" && (
          <div role="alert">
            <BubblesMascot size={80} mood="resting" animated={false} className="mx-auto" />
            <h1 className="m-0 mt-4 font-display text-h2">{state.gone ? "This link is no longer active." : "We couldn't open this link"}</h1>
            <p className="m-0 mt-2 text-body text-muted">
              {state.gone ? "The person who shared it may have stopped sharing, or the link may have expired. You can ask them for a new one." : state.message}
            </p>
            {!state.gone && (
              <button type="button" onClick={() => void load()} className="bubbles-press mt-4 inline-flex min-h-[44px] items-center rounded-full border-2 border-ink bg-surface px-5 text-body-sm font-extrabold">
                Try again
              </button>
            )}
          </div>
        )}

        {state.status === "ready" && (
          <div>
            <BubblesMascot size={80} mood="calm" className="mx-auto" />
            <h1 className="m-0 mt-4 font-display text-h2">Shared with you</h1>
            <p className="m-0 mt-1 text-body-sm font-bold text-muted">
              {(() => {
                const left = daysLeft(state.data.expires_at);
                return left === null ? state.data.label : `${state.data.label} · this link works for ${left} more day${left === 1 ? "" : "s"}`;
              })()}
            </p>
            {state.data.sections.length === 0 ? (
              <p className="m-0 mt-5 text-body font-bold text-muted">There is nothing to show right now.</p>
            ) : (
              state.data.sections.map((section) => <SectionCard key={section.key} section={section} idPrefix="partner" />)
            )}
            <p className="m-0 mt-5 text-body-sm text-muted">{state.data.notice}</p>
          </div>
        )}
      </div>
    </main>
  );
}
