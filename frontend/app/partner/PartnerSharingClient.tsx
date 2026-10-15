"use client";

import { useState, type ReactNode } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, HubPage, PILL, Skeleton } from "../../components/hub/HubKit";
import { ErrorNotice, INPUT, LiveRegion, QueryView } from "../../components/wellness/ui";
import { useWellnessQuery, useWellnessSend } from "../../components/wellness/useWellness";
import {
  EXPIRY_OPTIONS,
  NAME_MAX,
  NOTE_MAX,
  canSave,
  codeIsComplete,
  daysLeft,
  formatCodeInput,
  hoursLeft,
  inviteMessage,
  shareLink,
  whatsappLink,
  type PartnerSharingStatus,
  type ShareCategory,
  type ShareKey,
  type SharedWithMe,
} from "../lib/partner-sharing";
import { SectionCard } from "./SectionCard";

export function PartnerSharingClient() {
  return (
    <HubPage title="Partner sharing">
      <PartnerSharing />
    </HubPage>
  );
}

function PartnerSharing() {
  const [status, reloadStatus] = useWellnessQuery<PartnerSharingStatus>("/partner-sharing", { tz: false });
  const [mine, reloadMine] = useWellnessQuery<SharedWithMe>("/partner-sharing/shared-with-me", { tz: false });
  const reload = () => { reloadStatus(); reloadMine(); };
  const hasShares = mine.status === "ready" && mine.data.shares.length > 0;
  const skeleton = <div className="space-y-3"><Skeleton className="h-40 rounded-3xl" /><Skeleton className="h-40 rounded-3xl" /></div>;
  const withYou = (
    <QueryView query={mine} onRetry={reloadMine} what="what is shared with you" skeleton={skeleton}>
      {(data) => <SharedWithYou data={data} reload={reload} />}
    </QueryView>
  );
  return (
    <div className="space-y-6">
      <header className="bubbles-rise">
        <h1 className="text-h1 text-ink">Partner sharing</h1>
        <p className="mt-1 text-body font-semibold text-muted">
          Choose exactly what one trusted person can see, connect them to Bubbles, and stop whenever you like. Nothing is shared until you say so.
        </p>
      </header>

      {/* Your own settings come first unless someone is already sharing with you. */}
      {hasShares && withYou}
      <QueryView query={status} onRetry={reloadStatus} what="your sharing settings" skeleton={skeleton}>
        {(data) => <YourSharing data={data} reload={reload} />}
      </QueryView>
      {!hasShares && withYou}
    </div>
  );
}

/* ── What others share with me ───────────────────────────────────────────────── */

function SharedWithYou({ data, reload }: { data: SharedWithMe; reload: () => void }) {
  const send = useWellnessSend();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [said, setSaid] = useState("");

  async function connect() {
    setBusy(true);
    setError("");
    const result = await send<{ from_name: string }>("/partner-sharing/connect", "POST", { code, name }, { tz: false });
    setBusy(false);
    if (!result.ok) return setError(result.message);
    setCode("");
    setSaid(`You're connected. ${result.data.from_name} can stop sharing at any time, and so can you.`);
    reload();
  }

  async function leave(id: string) {
    if (!window.confirm("Stop seeing their summary? They can see in their settings that you left.")) return;
    setBusy(true);
    const result = await send(`/partner-sharing/shared-with-me/${id}`, "DELETE", undefined, { tz: false });
    setBusy(false);
    if (!result.ok) return setError(result.message);
    setSaid("You've left. You no longer see their summary.");
    reload();
  }

  return (
    <section aria-labelledby="with-you" className={`${CARD} space-y-4 p-5`}>
      <LiveRegion message={said} />
      <h2 id="with-you" className="m-0 font-display text-h3 text-ink">Shared with you</h2>
      {data.shares.length === 0 && <p className="m-0 text-body-sm text-muted">Nobody is sharing with you yet. If someone gave you a code, enter it below.</p>}
      {data.shares.map((share) => (
        <article key={share.id} aria-label={`Shared by ${share.from_name}`} className="rounded-3xl border border-line p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="m-0 font-display text-h4 text-ink">From {share.from_name}</p>
            <button type="button" className={BTN_SECONDARY} disabled={busy} onClick={() => void leave(share.id)}>Leave</button>
          </div>
          {share.sections.length === 0 ? <p className="m-0 mt-2 text-body-sm text-muted">There is nothing to show right now.</p>
            : share.sections.map((s) => <SectionCard key={s.key} section={s} idPrefix={`share-${share.id}`} />)}
          <p className="m-0 mt-3 text-body-sm text-muted">{share.notice}</p>
        </article>
      ))}
      {error && <ErrorNotice message={error} />}
      <form className="space-y-3 rounded-2xl bg-blush p-4" onSubmit={(e) => { e.preventDefault(); if (codeIsComplete(code)) void connect(); }}>
        <p className="m-0 text-body font-extrabold text-ink">Got a code from someone?</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="connect-code" className="mb-1 block text-body-sm font-bold text-ink-soft">Invite code</label>
            <input id="connect-code" className={`${INPUT} uppercase tracking-widest`} inputMode="text" autoComplete="off" autoCapitalize="characters" placeholder="ABCD-EFGH"
              value={code} onChange={(e) => setCode(formatCodeInput(e.target.value))} />
          </div>
          <div>
            <label htmlFor="connect-name" className="mb-1 block text-body-sm font-bold text-ink-soft">Your name (they will see it)</label>
            <input id="connect-name" className={INPUT} maxLength={NAME_MAX} placeholder="For example: Arjun" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        </div>
        <button type="submit" className={BTN_PRIMARY} disabled={busy || !codeIsComplete(code)}>{busy ? "Connecting…" : "Connect"}</button>
      </form>
    </section>
  );
}

/* ── What I share ────────────────────────────────────────────────────────────── */

function YourSharing({ data, reload }: { data: PartnerSharingStatus; reload: () => void }) {
  const send = useWellnessSend();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [said, setSaid] = useState("");
  const [revealed, setRevealed] = useState<{ kind: "code" | "link"; value: string; text: string } | null>(null);
  const [days, setDays] = useState<number>(30);

  async function call<T>(path: string, method: "POST" | "PUT" | "DELETE", body: unknown, done: string): Promise<T | null> {
    setBusy(true);
    setError("");
    const result = await send<T>(path, method, body, { tz: false });
    setBusy(false);
    if (!result.ok) { setError(result.message); return null; }
    setSaid(done);
    reload();
    return result.data;
  }

  async function saveSettings(b: { categories: ShareKey[]; note: string; owner_name: string }) {
    await call<PartnerSharingStatus>("/partner-sharing/settings", "PUT", b, "Saved. This applies straight away to anyone connected.");
  }

  async function makeInvite() {
    const r = await call<PartnerSharingStatus>("/partner-sharing/invite", "POST", undefined, "Your invite code is ready.");
    if (r?.code) setRevealed({ kind: "code", value: r.code, text: inviteMessage(r.code, window.location.origin) });
  }

  async function makeLink() {
    const r = await call<PartnerSharingStatus>("/partner-sharing/link", "POST", { expires_in_days: days }, "Your link is ready.");
    if (r?.token) {
      const url = shareLink(window.location.origin, r.token);
      setRevealed({ kind: "link", value: url, text: `I'm sharing a few things with you on Bubbles: ${url}` });
    }
  }

  async function confirmThen(message: string, path: string, done: string) {
    if (!window.confirm(message)) return;
    setRevealed(null);
    await call<PartnerSharingStatus>(path, "DELETE", undefined, done);
  }

  const left = daysLeft(data.link.expires_at);
  const hours = hoursLeft(data.invite.expires_at);

  return (
    <>
      <LiveRegion message={said} />
      {error && <ErrorNotice message={error} />}

      <section aria-labelledby="what-share" className={`${CARD} space-y-4 p-5`}>
        <h2 id="what-share" className="m-0 font-display text-h3 text-ink">What you share</h2>
        <Chooser key={`${data.categories.join()}|${data.note}|${data.owner_name}`} data={data} busy={busy} onSubmit={saveSettings} />
      </section>

      {data.configured && (
        <section aria-labelledby="who-sees" className={`${CARD} space-y-5 p-5`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="who-sees" className="m-0 font-display text-h3 text-ink">Who can see it</h2>
            <span className={`${PILL} ${data.sharing ? "bg-tint-mint text-bubbles-mint-deep" : "bg-blush text-ink-soft"}`}>{data.sharing ? "Sharing is on" : "Not shared with anyone yet"}</span>
          </div>

          {revealed && <Reveal reveal={revealed} onDone={() => setRevealed(null)} />}

          <div className="space-y-3 rounded-3xl border border-line p-4">
            <h3 className="m-0 text-body font-extrabold text-ink">Connect their Bubbles account (recommended)</h3>
            {data.connection ? (
              <>
                <p className="m-0 text-body-sm text-muted">Connected with <strong>{data.connection.name}</strong> (the name they typed) since {new Date(data.connection.since).toLocaleDateString()}. They see exactly what you chose above.</p>
                <button type="button" className={BTN_SECONDARY} disabled={busy} onClick={() => void confirmThen(`Disconnect ${data.connection?.name}? They stop seeing your summary straight away.`, "/partner-sharing/connection", "Disconnected. They no longer see anything.")}>Disconnect</button>
              </>
            ) : (
              <>
                <p className="m-0 text-body-sm text-muted">They sign in to their own Bubbles account and enter a one-time code. You can disconnect them at any time, and they can leave too.</p>
                {data.invite.active && <p className="m-0 text-body-sm font-bold text-ink-soft">An invite is waiting{hours !== null ? ` (about ${hours} hour${hours === 1 ? "" : "s"} left)` : ""}. Codes are shown only once; make a new one to see it again.</p>}
                <div className="flex flex-wrap gap-2">
                  <button type="button" className={BTN_PRIMARY} disabled={busy} onClick={() => void makeInvite()}>{data.invite.active ? "Make a new code" : "Make an invite code"}</button>
                  {data.invite.active && <button type="button" className={BTN_SECONDARY} disabled={busy} onClick={() => void confirmThen("Cancel the invite code?", "/partner-sharing/invite", "Invite cancelled.")}>Cancel the code</button>}
                </div>
              </>
            )}
          </div>

          <div className="space-y-3 rounded-3xl border border-line p-4">
            <h3 className="m-0 text-body font-extrabold text-ink">Or a quick link (no account needed)</h3>
            <p className="m-0 text-body-sm text-muted">Anyone who has the link can see your summary until it expires, so send it only to someone you trust.</p>
            {data.link.active && (
              <p className="m-0 text-body-sm font-bold text-ink-soft">
                Link on · {left} day{left === 1 ? "" : "s"} left · opened {data.link.views.count} time{data.link.views.count === 1 ? "" : "s"} (we never record who).
              </p>
            )}
            {data.link.expired && <p className="m-0 text-body-sm font-bold text-ink-soft">Your last link expired.</p>}
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <label htmlFor="link-days" className="mb-1 block text-body-sm font-bold text-ink-soft">Works for</label>
                <select id="link-days" className={INPUT} value={days} onChange={(e) => setDays(Number(e.target.value))}>
                  {EXPIRY_OPTIONS.map((d) => <option key={d} value={d}>{d} days</option>)}
                </select>
              </div>
              <button type="button" className={BTN_PRIMARY} disabled={busy} onClick={() => void makeLink()}>{data.link.active ? "Make a new link" : "Make a link"}</button>
              {data.link.active && <button type="button" className={BTN_SECONDARY} disabled={busy} onClick={() => void confirmThen("Turn the link off? It stops working straight away.", "/partner-sharing/link", "The link no longer works.")}>Turn link off</button>}
            </div>
          </div>

          <button type="button" className={BTN_SECONDARY} disabled={busy} onClick={() => void confirmThen("Stop all sharing? Every link, code and connection stops working straight away, and your choices are cleared.", "/partner-sharing", "All sharing stopped.")}>
            Stop all sharing
          </button>
        </section>
      )}

      <section aria-labelledby="safety" className={`${CARD} space-y-2 p-5`}>
        <h2 id="safety" className="m-0 font-display text-h4 text-ink">If sharing ever feels unsafe</h2>
        <p className="m-0 text-body-sm text-muted">
          You can stop everything with one tap above, and it takes effect immediately. If you are worried about your safety, call 112 (emergency) or the Women Helpline 181.
          For emotional support, Tele-MANAS is free on 14416.
        </p>
      </section>

      <section aria-labelledby="never-shared" className={`${CARD} space-y-2 p-5`}>
        <h2 id="never-shared" className="m-0 font-display text-h4 text-ink">What can never be shared</h2>
        <ul className="m-0 list-disc space-y-1 pl-5 text-body-sm text-muted">
          {data.never_shared.map((x) => <li key={x}>{x}</li>)}
        </ul>
        <p className="m-0 text-body-sm text-muted">The person you share with sees short summaries, never your logs.</p>
      </section>
    </>
  );
}

function Chooser({ data, busy, onSubmit }: {
  data: PartnerSharingStatus; busy: boolean;
  onSubmit: (b: { categories: ShareKey[]; note: string; owner_name: string }) => void;
}) {
  const [picked, setPicked] = useState<ShareKey[]>(data.categories);
  const [note, setNote] = useState(data.note);
  const [name, setName] = useState(data.owner_name);
  const toggle = (k: ShareKey) => setPicked((cur) => (cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k]));
  const ok = canSave(picked, note);

  return (
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (ok) onSubmit({ categories: picked, note, owner_name: name }); }}>
      <fieldset className="m-0 space-y-2 border-0 p-0">
        <legend className="mb-2 text-body font-extrabold text-ink">What can they see?</legend>
        {data.available.map((c: ShareCategory) => (
          <label key={c.key} className="flex cursor-pointer items-start gap-3 rounded-2xl bg-blush px-4 py-3">
            <input type="checkbox" className="mt-1 h-5 w-5" checked={picked.includes(c.key)} onChange={() => toggle(c.key)} />
            <span>
              <span className="block text-body font-extrabold text-ink">{c.label}</span>
              <span className="block text-body-sm text-muted">{c.description}</span>
            </span>
          </label>
        ))}
      </fieldset>

      {picked.includes("support_note") && (
        <div>
          <label htmlFor="partner-note" className="mb-1 block text-body font-extrabold text-ink">Your note</label>
          <textarea id="partner-note" className={INPUT} rows={3} maxLength={NOTE_MAX} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder="For example: I get tired and quiet before my period. A cup of tea and some space helps." />
          <p className="m-0 mt-1 text-body-sm text-muted">{note.length}/{NOTE_MAX}</p>
        </div>
      )}

      <div>
        <label htmlFor="owner-name" className="mb-1 block text-body font-extrabold text-ink">The name they will see (optional)</label>
        <input id="owner-name" className={INPUT} maxLength={NAME_MAX} value={name} onChange={(e) => setName(e.target.value)} placeholder="For example: Riya" />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button type="submit" className={BTN_PRIMARY} disabled={busy || !ok}>{busy ? "Saving…" : data.configured ? "Save changes" : "Save my choices"}</button>
        {picked.length === 0 && <span className="text-body-sm text-muted">Tick at least one thing to share.</span>}
        {!ok && picked.length > 0 && <span className="text-body-sm text-muted">Add your note, or untick “A note from you”.</span>}
      </div>
    </form>
  );
}

function Reveal({ reveal, onDone }: { reveal: { kind: "code" | "link"; value: string; text: string }; onDone: () => void }): ReactNode {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try { await navigator.clipboard.writeText(reveal.value); setCopied(true); } catch { setCopied(false); }
  }
  return (
    <div role="status" className="space-y-3 rounded-3xl border border-bubbles-mint bg-tint-mint p-4">
      <p className="m-0 text-body font-extrabold text-ink">{reveal.kind === "code" ? "Your invite code" : "Your link"}</p>
      <p className="m-0 text-body-sm font-semibold text-ink-soft">Copy it now. For your privacy we show it only this once.</p>
      <input readOnly aria-label={reveal.kind === "code" ? "Your invite code" : "Your partner link"} className={`${INPUT} ${reveal.kind === "code" ? "text-center font-display text-h3 tracking-widest" : ""}`} value={reveal.value} onFocus={(e) => e.currentTarget.select()} />
      <div className="flex flex-wrap gap-2">
        <button type="button" className={BTN_PRIMARY} onClick={() => void copy()}>{copied ? "Copied" : reveal.kind === "code" ? "Copy code" : "Copy link"}</button>
        <a className={`${BTN_SECONDARY} no-underline`} href={whatsappLink(reveal.text)} target="_blank" rel="noopener noreferrer">Share on WhatsApp</a>
        <button type="button" className={BTN_SECONDARY} onClick={onDone}>I&apos;ve saved it</button>
      </div>
    </div>
  );
}
