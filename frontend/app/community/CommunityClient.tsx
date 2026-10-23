"use client";

// The community: a feed with topic chips, one big "Ask or share" button, a closed Comments row per post, and My posts.
// Nothing here knows who wrote a post; the server only ever sends an alias.

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { BubblesMascot } from "../../components/BubblesMascot";
import { BTN_PRIMARY, BTN_SECONDARY, SECTION, Skeleton } from "../../components/hub/HubKit";
import { TrackerShell } from "../../components/tracking/kit";
import { useWellnessSend } from "../../components/wellness/useWellness";
import { ErrorNotice, INPUT, LiveRegion, Notice, Switch } from "../../components/wellness/ui";
import {
  TOPIC_LABELS, appendPage, applyReaction, closedMessage, postingHint, statusWord, topicLabel,
  type CommunityPost, type CommunityStatus, type ReactionKind, type Support,
} from "./community";

type Page = { posts: CommunityPost[]; next_cursor: string | null };
type Send = ReturnType<typeof useWellnessSend>;
const REASONS: [string, string][] = [["unkind", "Unkind"], ["unsafe_advice", "Unsafe advice"], ["spam", "Spam"], ["private_info", "Private info"], ["sexual", "Sexual"], ["other", "Something else"]];
const CHIP = "bubbles-press min-h-[44px] shrink-0 rounded-full border px-4 text-body-sm font-extrabold";
const CHIP_ON = "border-bubbles-grape bg-tint-grape text-bubbles-grape-deep";
const CHIP_OFF = "border-line bg-surface text-ink-soft";
const SMALL = "min-h-[44px] rounded-full px-3 text-chip font-extrabold text-ink-soft hover:text-ink";
const NO_TZ = { tz: false };

export function CommunityClient() {
  return (
    <TrackerShell title="Community">
      <h1 className="sr-only">Community</h1>
      <Community />
    </TrackerShell>
  );
}

/** Urgent or crisis wording in a post: a caring banner, never the mascot. */
function SupportBanner({ support, onClose }: { support: NonNullable<Support>; onClose: () => void }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    ref.current?.focus();
  }, [support]);
  return (
    <section ref={ref} role="alert" tabIndex={-1} aria-label="Support" className="rounded-3xl border-4 border-bubbles-urgent bg-tint-urgent p-5 outline-none">
      <p className="m-0 text-body font-bold text-ink">{support.message}</p>
      <p className="m-0 mt-3 text-body-sm font-semibold text-ink-soft">{support.lines}</p>
      <button type="button" onClick={onClose} className={`${BTN_SECONDARY} mt-4`}>I&apos;ve read this</button>
    </section>
  );
}

function Community() {
  const send = useWellnessSend();
  const [status, setStatus] = useState<CommunityStatus | null>(null);
  const [failed, setFailed] = useState("");
  const [topic, setTopic] = useState<string | null>(null);
  const [mine, setMine] = useState(false);
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sheet, setSheet] = useState(false);
  const [support, setSupport] = useState<Support>(null);
  const [said, setSaid] = useState("");
  const latest = useRef(0);

  const load = useCallback(async (after: string | null) => {
    const id = ++latest.current;
    const q = new URLSearchParams();
    if (topic) q.set("topic", topic);
    if (mine) q.set("mine", "true");
    if (after) q.set("cursor", after);
    setLoading(true);
    const r = await send<Page>(`/community/posts?${q}`, "GET", undefined, NO_TZ);
    if (id !== latest.current) return;
    setLoading(false);
    if (!r.ok) return setFailed(r.message);
    setFailed("");
    setPosts((cur) => (after ? appendPage(cur, r.data.posts) : r.data.posts));
    setCursor(r.data.next_cursor);
  }, [send, topic, mine]);

  useEffect(() => {
    void (async () => {
      const r = await send<CommunityStatus>("/community/status", "GET", undefined, NO_TZ);
      if (r.ok) setStatus(r.data);
      else setFailed(r.message);
    })();
  }, [send]);
  const canRead = status?.can_read;
  useEffect(() => {
    if (canRead) void load(null);
  }, [canRead, load]);

  if (!status) return failed ? <ErrorNotice message={failed} /> : <Skeleton className="h-64 rounded-3xl" />;
  const closed = closedMessage(status);
  if (closed) return <Notice tone="calm">{closed}</Notice>;

  const hint = postingHint(status);
  const note = async (path: string, method: "POST" | "DELETE", body: object | undefined, ok: string) => {
    const r = await send(path, method, body, NO_TZ);
    setSaid(r.ok ? ok : r.message);
    return r.ok;
  };
  const react = async (post: CommunityPost, kind: ReactionKind) => {
    const r = await send<{ on: boolean }>("/community/reactions", "POST", { target: `post:${post.id}`, kind }, NO_TZ);
    if (r.ok) setPosts((cur) => cur.map((p) => (p.id === post.id ? applyReaction(p, kind, r.data.on) : p)));
    else setSaid(r.message);
  };
  const drop = (id: string) => setPosts((cur) => cur.filter((p) => p.id !== id));

  return (
    <div className="flex flex-col gap-4">
      {support && <SupportBanner support={support} onClose={() => setSupport(null)} />}
      <div className="flex flex-col gap-2">
        <button type="button" disabled={!status.can_post} onClick={() => setSheet(true)} className={`${BTN_PRIMARY} min-h-[56px] w-full text-lg`}>
          Ask or share
        </button>
        {hint && (
          <p className="m-0 text-body-sm text-muted">
            {hint} <Link href="/privacy-choices" className="font-extrabold text-bubbles-grape-deep underline">Privacy choices</Link>
          </p>
        )}
      </div>

      <div role="group" aria-label="Topics" className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0 [scrollbar-width:none]">
        {[["", "All"] as const, ...status.topics.map((t) => [t, topicLabel(t)] as const)].map(([id, label]) => {
          const on = (topic ?? "") === id && !mine;
          return (
            <button key={id} type="button" aria-pressed={on} onClick={() => { setMine(false); setTopic(id || null); }} className={`${CHIP} ${on ? CHIP_ON : CHIP_OFF}`}>
              {label}
            </button>
          );
        })}
        <button type="button" aria-pressed={mine} onClick={() => { setTopic(null); setMine(true); }} className={`${CHIP} ${mine ? CHIP_ON : CHIP_OFF}`}>
          My posts
        </button>
      </div>

      {failed && <ErrorNotice message={failed} />}
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {posts.map((p) => (
          <PostCard key={p.id} post={p} send={send} canPost={status.can_post} limit={status.limits.comment} onReact={react}
            onDelete={async () => { if (await note(`/community/posts/${p.id}`, "DELETE", undefined, "Deleted.")) drop(p.id); }}
            onSaid={setSaid} onSupport={setSupport} onBlocked={() => drop(p.id)} />
        ))}
      </ul>
      {loading && <Skeleton className="h-32 rounded-3xl" />}
      {!loading && !failed && posts.length === 0 && (
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          <BubblesMascot size={96} mood="resting" title="Bubbles" />
          <p className="m-0 text-body font-extrabold text-ink">{mine ? "You have not posted yet." : "Nothing here yet."}</p>
          <p className="m-0 text-body-sm text-muted">{mine ? "Whatever you share will show up here." : "Be the first to ask or share."}</p>
        </div>
      )}
      {cursor && !loading && <button type="button" onClick={() => void load(cursor)} className={`${BTN_SECONDARY} self-center`}>Show more</button>}

      <p className="m-0 text-center text-body-sm text-muted">{status.disclaimer}</p>
      <LiveRegion message={said} />
      {said && <p className="m-0 text-center text-body-sm font-bold text-ink-soft">{said}</p>}
      {sheet && (
        <AskSheet send={send} topics={status.topics} limit={status.limits.post} onClose={() => setSheet(false)}
          onPosted={(post, s) => {
            setSheet(false);
            setSupport(s);
            setSaid(post.status === "visible" ? "Shared." : post.note ?? "Saved. It is waiting for a quick review.");
            setTopic(null);
            setMine(true);
            if (mine && !topic) void load(null);
          }} />
      )}
    </div>
  );
}

function PostCard({ post, send, canPost, limit, onReact, onDelete, onSaid, onSupport, onBlocked }: {
  post: CommunityPost; send: Send; canPost: boolean; limit: number; onReact: (p: CommunityPost, k: ReactionKind) => void; onDelete: () => void;
  onSaid: (m: string) => void; onSupport: (s: Support) => void; onBlocked: () => void;
}) {
  const [menu, setMenu] = useState(false);
  const shown = post.status === undefined || post.status === "visible";
  const report = async (reason: string) => {
    const r = await send<{ message: string }>("/community/reports", "POST", { target: `post:${post.id}`, reason }, NO_TZ);
    onSaid(r.ok ? r.data.message : r.message);
    setMenu(false);
  };
  const block = async () => {
    const r = await send("/community/blocks", "POST", { target: `post:${post.id}` }, NO_TZ);
    if (r.ok) onBlocked();
    else onSaid(r.message);
  };
  const pill = (kind: ReactionKind, label: string) => (
    <button type="button" aria-pressed={post.my_reactions.includes(kind)} disabled={!canPost || !shown} onClick={() => onReact(post, kind)}
      className={`${CHIP} ${post.my_reactions.includes(kind) ? CHIP_ON : CHIP_OFF}`}>
      {label} {post.reactions[kind]}
    </button>
  );
  return (
    <li className={`${SECTION}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 text-body-sm text-muted">
        <span><span className="font-extrabold text-ink">{post.alias}</span>{post.topic ? `, ${topicLabel(post.topic)}` : ""}</span>
        <span>{new Date(post.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</span>
      </div>
      <p className="m-0 mt-2 whitespace-pre-line break-words text-body text-ink">{post.body}</p>
      {post.mine && !shown && (
        <div className="mt-3"><Notice tone="warm" title={statusWord(post.status)}>{post.note}</Notice></div>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {pill("me_too", "Me too")}
        {pill("helpful", "Helpful")}
        <span className="grow" />
        {post.mine ? <button type="button" onClick={onDelete} aria-label={`Delete your post from ${post.alias}`} className={SMALL}>Delete</button>
          : <button type="button" aria-expanded={menu} aria-label={`Report or block ${post.alias}`} onClick={() => setMenu((m) => !m)} className={SMALL}>Report or block</button>}
      </div>
      {menu && (
        <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Report this post">
          {REASONS.map(([id, label]) => <button key={id} type="button" onClick={() => void report(id)} className={`${CHIP} ${CHIP_OFF}`}>{label}</button>)}
          <button type="button" onClick={() => void block()} className={`${CHIP} border-line-strong bg-surface text-ink`}>Block this person</button>
        </div>
      )}
      {shown && (
        <details className="mt-3 rounded-2xl bg-blush">
          <summary className="flex min-h-[44px] cursor-pointer items-center px-4 text-body-sm font-extrabold text-ink-soft">
            Comments{post.comment_count ? ` (${post.comment_count})` : ""}
          </summary>
          <Comments postId={post.id} send={send} canPost={canPost} limit={limit} onSaid={onSaid} onSupport={onSupport} />
        </details>
      )}
    </li>
  );
}

type Comment = { id: string; alias: string; body: string; mine: boolean; status?: string; note?: string };

function Comments({ postId, send, canPost, limit, onSaid, onSupport }: {
  postId: string; send: Send; canPost: boolean; limit: number; onSaid: (m: string) => void; onSupport: (s: Support) => void;
}) {
  const [items, setItems] = useState<Comment[] | null>(null);
  const [text, setText] = useState("");
  const [anon, setAnon] = useState(true);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const r = await send<{ comments: Comment[] }>(`/community/posts/${postId}/comments`, "GET", undefined, NO_TZ);
    if (r.ok) setItems(r.data.comments.slice().reverse());
    else onSaid(r.message);
  }, [send, postId, onSaid]);
  useEffect(() => {
    void load();
  }, [load]);
  const add = async () => {
    setBusy(true);
    const r = await send<{ comment: Comment; support: Support }>(`/community/posts/${postId}/comments`, "POST", { body: text.trim(), anonymous: anon }, NO_TZ);
    setBusy(false);
    if (!r.ok) return onSaid(r.message);
    setText("");
    onSupport(r.data.support);
    onSaid(r.data.comment.status === "visible" ? "Added." : r.data.comment.note ?? "Saved. It is waiting for a quick review.");
    void load();
  };
  const del = async (id: string) => {
    const r = await send(`/community/comments/${id}`, "DELETE", undefined, NO_TZ);
    if (r.ok) void load();
    else onSaid(r.message);
  };
  return (
    <div className="flex flex-col gap-3 px-4 pb-4">
      {items === null ? <Skeleton className="h-10 rounded-2xl" /> : items.length === 0 ? <p className="m-0 text-body-sm text-muted">No comments yet.</p> : (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {items.map((c) => (
            <li key={c.id} className="text-body-sm">
              <span className="font-extrabold text-ink">{c.alias}</span>
              <span className="text-ink-soft">{` ${c.body}`}</span>
              {c.mine && c.status && c.status !== "visible" && <span className="text-muted">{` (${c.status === "held" ? "waiting for review" : "not shown"})`}</span>}
              {c.mine && <button type="button" onClick={() => void del(c.id)} aria-label="Delete your comment" className="ml-2 min-h-[44px] text-chip font-extrabold text-ink-soft">Delete</button>}
            </li>
          ))}
        </ul>
      )}
      {canPost && (
        <div className="flex flex-col gap-2">
          <label htmlFor={`c-${postId}`} className="sr-only">Your comment</label>
          <textarea id={`c-${postId}`} rows={2} value={text} maxLength={limit} onChange={(e) => setText(e.target.value)} placeholder="Say something kind." className={`${INPUT} resize-y`} />
          <label className="flex min-h-[44px] items-center gap-2 text-body-sm text-ink-soft">
            <input type="checkbox" checked={anon} onChange={(e) => setAnon(e.target.checked)} className="h-5 w-5" /> Anonymous
          </label>
          <button type="button" disabled={busy || !text.trim()} onClick={() => void add()} className={`${BTN_SECONDARY} self-start`}>Add comment</button>
        </div>
      )}
    </div>
  );
}

function AskSheet({ send, topics, limit, onClose, onPosted }: {
  send: Send; topics: string[]; limit: number; onClose: () => void; onPosted: (post: CommunityPost, support: Support) => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [topic, setTopic] = useState(topics.includes("talk") ? "talk" : topics[0]);
  const [anon, setAnon] = useState(true);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);
  const post = async () => {
    setBusy(true);
    setError("");
    const r = await send<{ post: CommunityPost; support: Support }>("/community/posts", "POST", { topic, body: body.trim(), anonymous: anon }, NO_TZ);
    setBusy(false);
    if (!r.ok) return setError(`${r.message} What you wrote is still here.`);
    onPosted(r.data.post, r.data.support);
  };
  return (
    <dialog ref={ref} aria-labelledby="ask-title" onClose={onClose} onClick={(e) => { if (e.target === e.currentTarget) ref.current?.close(); }}
      className="m-auto max-h-[90dvh] w-[min(36rem,calc(100vw-2rem))] overflow-y-auto rounded-[24px] bg-surface p-0 text-ink backdrop:bg-ink/55">
      <div className="flex flex-col gap-4 p-6">
        <h2 id="ask-title" className="m-0 font-display text-h3">Ask or share</h2>
        <Switch label="Post anonymously" hint={anon ? "Others see a made-up name like Quiet Otter." : "Others see your first name."} checked={anon} onChange={setAnon} offWord="Named" onWord="Anonymous" />
        <div role="group" aria-label="Topic" className="flex flex-wrap gap-2">
          {topics.map((t) => (
            <button key={t} type="button" aria-pressed={topic === t} onClick={() => setTopic(t)} className={`${CHIP} ${topic === t ? CHIP_ON : CHIP_OFF}`}>
              {TOPIC_LABELS[t] ?? t}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="ask-body" className="text-body font-extrabold">What is on your mind?</label>
          <textarea id="ask-body" rows={6} value={body} maxLength={limit} onChange={(e) => setBody(e.target.value)} className={`${INPUT} resize-y`} />
          <p className="m-0 text-right text-body-sm text-muted">{body.length} / {limit}</p>
        </div>
        {error && <ErrorNotice message={error} />}
        <div className="flex flex-wrap gap-3">
          <button type="button" disabled={busy || !body.trim()} onClick={() => void post()} className={BTN_PRIMARY}>{busy ? "Posting…" : "Post"}</button>
          <button type="button" onClick={() => ref.current?.close()} className={BTN_SECONDARY}>Cancel</button>
        </div>
      </div>
    </dialog>
  );
}
