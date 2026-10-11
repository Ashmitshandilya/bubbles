"use client";

import { useEffect, useId, useState } from "react";
import { useApi } from "../Providers";
import { CARD } from "../hub/HubKit";

/** Settings switch for "send my messages to an outside AI model". The server checks it before any message leaves; off means Bubbles still logs, shows patterns and handles emergencies. */
export function AiConsentRow() {
  const { fetchBubbles } = useApi();
  const [state, setState] = useState<"loading" | "on" | "off" | "error">("loading");
  const [busy, setBusy] = useState(false);
  const labelId = useId();
  const hintId = useId();

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const response = await fetchBubbles("/me/consent");
        const body = response.ok ? await response.json() : null;
        if (alive) setState(body && typeof body.ai_chat === "boolean" ? (body.ai_chat ? "on" : "off") : "error");
      } catch {
        if (alive) setState("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [fetchBubbles]);

  async function change(next: boolean) {
    setBusy(true);
    try {
      const response = await fetchBubbles("/me/consent", { method: "PUT", body: JSON.stringify({ ai_chat: next }) });
      const body = response.ok ? await response.json() : null;
      setState(body && typeof body.ai_chat === "boolean" ? (body.ai_chat ? "on" : "off") : "error");
    } catch {
      setState("error");
    } finally {
      setBusy(false);
    }
  }

  const on = state === "on";
  return (
    <div className={`${CARD} flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-4`}>
      <div className="min-w-0 max-w-[30rem]">
        <p id={labelId} className="m-0 font-bold text-ink">
          Outside AI model for open questions
        </p>
        <p id={hintId} className="m-0 mt-1 text-body-sm text-muted">
          {state === "error"
            ? "Bubbles couldn't check this just now."
            : "When on, Bubbles sends your message and a short summary of your own notes to an outside AI model to write its answer. When off, nothing is sent: logging, patterns and emergency help still work."}
        </p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-labelledby={labelId}
        aria-describedby={hintId}
        disabled={busy || state === "loading" || state === "error"}
        onClick={() => void change(!on)}
        className={`bubbles-press relative inline-flex h-8 w-14 shrink-0 items-center rounded-full border-2 transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
          on ? "border-bubbles-grape bg-bubbles-grape" : "border-line-strong bg-surface"
        }`}
      >
        <span aria-hidden="true" className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${on ? "translate-x-7" : "translate-x-1 !bg-line-strong"}`} />
      </button>
    </div>
  );
}
