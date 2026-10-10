"use client";

// Public page: what a partner sees. No login, no HubPage, no navigation. It makes one anonymous request (no
// Authorization header, no cookies). It deliberately does not use AuthProvider, which redirects visitors without a
// session to /login.

import { useCallback, useEffect, useState } from "react";
import { BubblesMascot } from "../../../../components/BubblesMascot";
import { formatRange } from "../../../lib/cycle-format";
import { partnerEndpoint, partnerErrorMessage } from "../../../lib/cycle-public";
import type { PartnerPublicResponse } from "../../../lib/cycle-types";

type State = { status: "loading" } | { status: "error"; message: string; gone: boolean } | { status: "ready"; data: PartnerPublicResponse };

export function PartnerClient({ token }: { token: string }) {
  const [state, setState] = useState<State>({ status: "loading" });
  // A sleeping free host can take about a minute to start; say so instead of looking stuck.
  const [slow, setSlow] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setState({ status: "loading" });
    setSlow(false);
    const slowTimer = window.setTimeout(() => setSlow(true), 4000);
    const timer = new AbortController();
    const timeout = window.setTimeout(() => timer.abort(), 65000);
    signal?.addEventListener("abort", () => timer.abort());
    try {
      const response = await fetch(partnerEndpoint(token), { cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal: timer.signal });
      if (!response.ok) {
        setState({ status: "error", message: partnerErrorMessage(response.status), gone: response.status === 404 || response.status === 410 });
        return;
      }
      setState({ status: "ready", data: (await response.json()) as PartnerPublicResponse });
    } catch {
      if (!signal?.aborted) setState({ status: "error", message: partnerErrorMessage(null), gone: false });
    } finally {
      window.clearTimeout(timeout);
      window.clearTimeout(slowTimer);
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
            <p className="mb-0 mt-4 text-body font-bold text-muted">{slow ? "Waking up Bubbles… this can take a moment." : "Opening the shared link…"}</p>
          </div>
        )}

        {state.status === "error" && (
          <div role="alert">
            <BubblesMascot size={80} mood="resting" animated={false} className="mx-auto" />
            <h1 className="m-0 mt-4 font-display text-h2">{state.gone ? "This link is no longer active." : "We couldn't open this link"}</h1>
            <p className="m-0 mt-2 text-body text-muted">
              {state.gone ? "The person who shared it may have turned sharing off. You can ask them for a new one." : state.message}
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
            <p className="m-0 mt-1 text-body-sm font-bold text-muted">{state.data.label}</p>
            <section aria-labelledby="partner-next" className="mt-5 rounded-3xl bg-tint-pink p-5 text-bubbles-pink-deep">
              <h2 id="partner-next" className="m-0 text-body-sm font-extrabold uppercase tracking-wide">Next period, estimated</h2>
              {state.data.next_period ? (
                <p className="m-0 mt-1 font-display text-h3">Between {formatRange(state.data.next_period.earliest, state.data.next_period.latest).replace(" to ", " and ")}</p>
              ) : (
                <p className="m-0 mt-1 text-body font-bold">No estimate is available right now.</p>
              )}
              {state.data.phase_hint && <p className="m-0 mt-2 text-body-sm font-semibold">{state.data.phase_hint}</p>}
            </section>
            <p className="m-0 mt-4 text-body-sm text-muted">{state.data.notice}</p>
          </div>
        )}
      </div>
    </main>
  );
}
