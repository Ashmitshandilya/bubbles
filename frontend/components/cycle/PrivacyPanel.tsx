"use client";

// Privacy: local-only switch, partner share link (token shown once) and a two-step "delete everything".

import { useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, useBubblesQuery } from "../hub/HubKit";
import { fmtDay } from "../../app/lib/cycle-format";
import type { DeleteResponse, PartnerViewResponse } from "../../app/lib/cycle-types";
import { useCycle } from "./CycleStore";
import { INPUT } from "./fields";
import { Card, InlineError, PanelError } from "./shared";

export function PrivacyPanel() {
  return (
    <Card labelledBy="cycle-privacy-title">
      <h3 id="cycle-privacy-title" className="m-0 font-display text-h3 text-ink">Privacy</h3>
      <div className="mt-4 space-y-6 divide-y-2 divide-line [&>*:not(:first-child)]:pt-6">
        <LocalOnly />
        <PartnerShare />
        <DeleteData />
      </div>
    </Card>
  );
}

function LocalOnly() {
  const { settings, saveSettings, announce } = useCycle();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const on = settings?.privacy.local_only ?? false;

  async function toggle() {
    setBusy(true);
    setError("");
    const failure = await saveSettings({ privacy: { local_only: !on } });
    setBusy(false);
    if (failure) setError(failure);
    else announce(!on ? "Cycle data is now kept out of chat, insights and the doctor timeline." : "Cycle data can now be used in chat, insights and the doctor timeline.");
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p id="cycle-local-label" className="m-0 text-body font-extrabold text-ink">Keep my cycle data out of Bubbles&apos; chat, insights and doctor timeline</p>
          <p id="cycle-local-help" className="m-0 mt-1 text-body-sm text-muted">
            When this is on, Bubbles does not use your cycle entries anywhere else in the app. You can still see them here. It is off by default so Bubbles can notice links, like sleep and your cycle.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-labelledby="cycle-local-label"
          aria-describedby="cycle-local-help"
          disabled={busy || !settings}
          onClick={toggle}
          className={`relative inline-flex h-11 w-[84px] shrink-0 items-center rounded-full border-2 px-1.5 text-[0.75rem] font-extrabold disabled:opacity-60 ${on ? "justify-start border-bubbles-pink-ink bg-tint-pink text-bubbles-pink-deep" : "justify-end border-line-strong bg-surface text-ink-soft"}`}
        >
          {on ? "On" : "Off"}
        </button>
      </div>
      {error && <div className="mt-2"><InlineError message={error} /></div>}
    </div>
  );
}

function PartnerShare() {
  const { call, announce } = useCycle();
  const [query, reload] = useBubblesQuery<PartnerViewResponse>("/cycle/partner-view");
  const [override, setOverride] = useState<PartnerViewResponse | null>(null);
  const [link, setLink] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");
  const [busy, setBusy] = useState(false);
  const view = override ?? (query.status === "ready" ? query.data : null);

  async function act(action: "create" | "revoke") {
    setBusy(true);
    setError("");
    setCopied("");
    const result = await call<PartnerViewResponse>("/cycle/partner-view", { method: "POST", body: JSON.stringify({ action }) });
    setBusy(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setOverride({ ...result.data, token: undefined });
    setLink(action === "create" && result.data.token ? `${window.location.origin}/cycle/partner/${result.data.token}` : "");
    announce(action === "create" ? "Partner link created." : "Partner link turned off.");
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied("Link copied.");
    } catch {
      setCopied("Copying is not allowed here. Select the link and copy it by hand.");
    }
  }

  return (
    <div>
      <p className="m-0 text-body font-extrabold text-ink">Share with a partner</p>
      <p className="m-0 mt-1 text-body-sm text-muted">
        A private link shows the next-period range only: no logs, symptoms or notes. Anyone with the link can see it, so share it carefully. You can turn it off any time.
      </p>
      {query.status === "loading" && !view && <p role="status" className="m-0 mt-2 text-body-sm text-muted">Loading…</p>}
      {query.status === "error" && !view && <div className="mt-3"><PanelError title="Sharing settings didn't load" message={query.message} onRetry={reload} /></div>}
      {view && (
        <div className="mt-3 space-y-3">
          {view.shares.length > 0 && (
            <p className="m-0 text-body-sm text-ink">Your partner can see: {view.shares.join(", ")}.</p>
          )}
          {link && (
            <div className="rounded-3xl bg-tint-sun p-4 text-bubbles-sun-deep">
              <label htmlFor="cycle-partner-link" className="block text-body-sm font-extrabold">Your link. It is shown only once, so copy it now.</label>
              <div className="mt-2 flex flex-wrap gap-2">
                <input id="cycle-partner-link" readOnly value={link} onFocus={(e) => e.currentTarget.select()} className={`${INPUT} min-w-[12rem] flex-1 text-ink`} />
                <button type="button" onClick={copy} className={BTN_SECONDARY}>Copy link</button>
              </div>
              {copied && <p role="status" className="m-0 mt-2 text-body-sm font-bold">{copied}</p>}
            </div>
          )}
          {view.enabled ? (
            <div className="flex flex-wrap items-center gap-3">
              <p className="m-0 text-body-sm font-bold text-bubbles-mint-deep">Sharing is on{view.created_at ? ` since ${fmtDay(view.created_at.slice(0, 10))}` : ""}.</p>
              <button type="button" disabled={busy} onClick={() => act("revoke")} className={BTN_SECONDARY}>Turn off sharing</button>
              <button type="button" disabled={busy} onClick={() => act("create")} className="min-h-[44px] rounded-full px-3 text-body-sm font-bold text-bubbles-pink-ink underline">Make a new link</button>
            </div>
          ) : (
            <button type="button" disabled={busy} onClick={() => act("create")} className={BTN_PRIMARY}>{busy ? "Working…" : "Create a private link"}</button>
          )}
        </div>
      )}
      {error && <div className="mt-2"><InlineError message={error} /></div>}
    </div>
  );
}

function DeleteData() {
  const { call, reloadAll, announce } = useCycle();
  const [step, setStep] = useState<0 | 1>(0);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  async function remove() {
    setBusy(true);
    setError("");
    const result = await call<DeleteResponse>("/cycle/data?confirm=yes", { method: "DELETE" });
    setBusy(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    const n = result.data.deleted.days;
    const message = `Deleted ${n} ${n === 1 ? "day" : "days"} of cycle entries and your cycle settings.`;
    setDone(message);
    announce(message);
    setStep(0);
    setText("");
    reloadAll();
  }

  return (
    <div>
      <p className="m-0 text-body font-extrabold text-ink">Delete all my cycle data</p>
      <p className="m-0 mt-1 text-body-sm text-muted">Removes every cycle entry, your cycle settings and any partner link. This cannot be undone.</p>
      {done && <p role="status" className="m-0 mt-2 text-body-sm font-bold text-bubbles-mint-deep">{done}</p>}
      {step === 0 ? (
        <button type="button" onClick={() => { setStep(1); setDone(""); }} className={`${BTN_SECONDARY} mt-3 border-bubbles-urgent text-bubbles-urgent`}>Delete all my cycle data…</button>
      ) : (
        <div className="mt-3 space-y-3 rounded-3xl border-2 border-bubbles-urgent bg-tint-urgent p-4 text-ink">
          <label htmlFor="cycle-delete" className="block text-body-sm font-extrabold">To confirm, type DELETE</label>
          <input id="cycle-delete" value={text} autoComplete="off" onChange={(e) => setText(e.target.value)} className={`${INPUT} max-w-[14rem]`} />
          <div className="flex flex-wrap gap-3">
            <button type="button" disabled={busy || text !== "DELETE"} onClick={remove} className="bubbles-press inline-flex min-h-[44px] items-center rounded-full bg-bubbles-urgent px-5 text-body-sm font-extrabold text-white disabled:opacity-50">
              {busy ? "Deleting…" : "Delete everything"}
            </button>
            <button type="button" onClick={() => { setStep(0); setText(""); }} className={BTN_SECONDARY}>Cancel</button>
          </div>
        </div>
      )}
      {error && <div className="mt-2"><InlineError message={error} /></div>}
    </div>
  );
}
