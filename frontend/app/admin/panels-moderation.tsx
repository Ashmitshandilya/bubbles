"use client";

// The Moderation tab: held and reported community items (crisis first), approve / remove / ban, alias lookup (logged on the server)
// and the audit log. The owner sees the text here because the owner is the data controller of the community (see the privacy notice).

import { useState } from "react";
import { BTN_SECONDARY } from "../../components/hub/HubKit";
import { responseFailure } from "../../lib/api";
import { humanize } from "./format";
import { CopyUid } from "./panels-live";
import { Empty, LoadState, Panel, Pill, Stat, useAdmin, useAdminQuery } from "./kit";

type Item = {
  target: string; kind: "post" | "comment"; alias: string; topic: string | null; body: string; created_at: string;
  reason_code: string | null; crisis: boolean; reports: number; report_reasons: string[];
};
type Queue = { items: Item[]; enabled: boolean; message: string | null };
type Status = { enabled: boolean; message: string | null; counts: Record<string, number>; banned: number };
type LogRow = { id?: string; target: string; action: string; reason_code: string | null; actor: string; created_at: string };

const ACT = "bubbles-press min-h-[44px] rounded-full border px-4 text-body-sm font-extrabold";

function QueueItem({ item, onDone }: { item: Item; onDone: () => void }) {
  const { adminFetch } = useAdmin();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [who, setWho] = useState<string | null>(null);
  const call = async (path: string, body: object) => {
    setBusy(true);
    setError("");
    try {
      const res = await adminFetch(path, { method: "POST", body: JSON.stringify(body) });
      if (!res.ok) {
        setError((await responseFailure(res)).message);
        return null;
      }
      return (await res.json()) as { user_id?: string };
    } finally {
      setBusy(false);
    }
  };
  const decide = async (action: "approve" | "remove" | "ban") => {
    if (action === "ban" && !window.confirm("Ban this person from the community and hold everything else they wrote?")) return;
    if (await call("/admin/community/decide", { target: item.target, action })) onDone();
  };
  const resolve = async () => {
    const r = await call("/admin/community/resolve", { target: item.target });
    if (r?.user_id) setWho(r.user_id);
  };
  return (
    <li className="rounded-2xl border border-line p-4">
      <div className="flex flex-wrap items-center gap-2 text-body-sm">
        {item.crisis && <Pill tone="urgent">Crisis wording, look first</Pill>}
        <Pill tone="plain">{item.kind === "post" ? "Post" : "Comment"}</Pill>
        <span className="font-extrabold">{item.alias}</span>
        {item.topic && <span className="text-muted">{humanize(item.topic)}</span>}
        <span className="ml-auto tabular-nums text-muted">{new Date(item.created_at).toLocaleString()}</span>
      </div>
      <p className="m-0 mt-3 whitespace-pre-line break-words text-body">{item.body}</p>
      <p className="m-0 mt-2 text-body-sm text-muted">
        {[item.reason_code ? `Held: ${humanize(item.reason_code)}` : null, item.reports ? `${item.reports} report${item.reports === 1 ? "" : "s"}` : null,
          item.report_reasons.length ? item.report_reasons.map(humanize).join(", ") : null].filter(Boolean).join(". ")}
      </p>
      {error && <p role="alert" className="m-0 mt-2 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" disabled={busy} onClick={() => void decide("approve")} aria-label={`Approve ${item.kind} by ${item.alias}`} className={`${ACT} border-bubbles-grape bg-tint-grape text-bubbles-grape-deep`}>Approve</button>
        <button type="button" disabled={busy} onClick={() => void decide("remove")} aria-label={`Remove ${item.kind} by ${item.alias}`} className={`${ACT} border-line-strong bg-surface text-ink`}>Remove</button>
        <button type="button" disabled={busy} onClick={() => void decide("ban")} aria-label={`Remove and ban ${item.kind} by ${item.alias}`} className={`${ACT} border-bubbles-urgent bg-surface text-ink`}>Remove and ban</button>
        <button type="button" disabled={busy} onClick={() => void resolve()} aria-label={`Who wrote this ${item.kind} by ${item.alias}`} className={`${ACT} border-line bg-surface text-ink-soft`}>Who wrote this</button>
      </div>
      {who && <div className="mt-2"><CopyUid uid={who} /></div>}
    </li>
  );
}

export function ModerationPanel() {
  const [status, reloadStatus] = useAdminQuery<Status>("/admin/community/status", 30);
  const [queue, reloadQueue] = useAdminQuery<Queue>("/admin/community/queue", 30);
  const [log, reloadLog] = useAdminQuery<{ log: LogRow[] }>("/admin/community/log?limit=50");
  const done = () => {
    reloadQueue();
    reloadStatus();
    reloadLog();
  };
  return (
    <div className="flex flex-col gap-4">
      <Panel title="Community" id="mod-status">
        <LoadState state={status} title="the community numbers" retry={reloadStatus} rows={1}>
          {(s) => (
            <>
              {!s.enabled && <Empty>{s.message ?? "The community is off."}</Empty>}
              <div className="grid grid-cols-2 divide-x divide-line sm:grid-cols-4">
                <Stat label="Posts shown" value={String(s.counts.posts_visible ?? 0)} />
                <Stat label="Posts waiting" value={String((s.counts.posts_held ?? 0) + (s.counts.comments_held ?? 0))} note="Including comments" />
                <Stat label="Removed" value={String((s.counts.posts_removed ?? 0) + (s.counts.comments_removed ?? 0))} />
                <Stat label="Banned" value={String(s.banned)} />
              </div>
            </>
          )}
        </LoadState>
      </Panel>
      <Panel title="Waiting for a decision" id="mod-queue">
        <LoadState state={queue} title="the review queue" retry={reloadQueue}>
          {(q) => q.items.length === 0 ? <Empty>Nothing is waiting.</Empty> : (
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {q.items.map((i) => <QueueItem key={i.target} item={i} onDone={done} />)}
            </ul>
          )}
        </LoadState>
      </Panel>
      <Panel title="What happened" id="mod-log" action={<button type="button" className={BTN_SECONDARY} onClick={reloadLog}>Refresh</button>}>
        <LoadState state={log} title="the moderation log" retry={reloadLog}>
          {(l) => l.log.length === 0 ? <Empty>No actions yet.</Empty> : (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {l.log.map((r, i) => (
                <li key={r.id ?? i} className="flex flex-wrap items-center gap-2 text-body-sm">
                  <span className="tabular-nums text-muted">{new Date(r.created_at).toLocaleString()}</span>
                  <Pill tone="plain">{humanize(r.action)}</Pill>
                  <span>{humanize(r.actor)}</span>
                  <code className="font-mono text-chip text-muted">{r.target}</code>
                  {r.reason_code && <span className="text-muted">{humanize(r.reason_code)}</span>}
                </li>
              ))}
            </ul>
          )}
        </LoadState>
      </Panel>
    </div>
  );
}
