"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar, MobileNav, ApiAlert } from "../../components/Navigation";
import { useAuth, useApi } from "../../components/Providers";
import { BubblesMascot } from "../../components/BubblesMascot";
import {
  adaptCorrection,
  adaptEvidence,
  adaptHealthEvents,
  adaptReplySafety,
  applyCorrection,
  confidenceLabel,
  isUrgentMessage,
  replaceId,
  upsertById,
} from "../lib/bubbles-events";
import { askHandle, readAsk } from "../lib/ask-handoff";
import { CHAT_TIMEOUT_MS, chatErrorMessage, isTimeoutError, needsFreshMessageId, resetsConversation } from "../lib/chat-flow";
import { parseRatings, ratingsPath, type Feedback, type FeedbackReason, type Rating } from "./feedback";
import {
  BubblesReply,
  ConversationList,
  Icon,
  ICONS,
  PromptCards,
  ThinkingBubble,
  type ChatMessage,
  type ConversationSummary,
  type EventStatus,
  type PromptCard,
} from "./ChatBits";

const MAX_MESSAGE = 8000; // ChatRequest.message max_length in backend/main.py
const PROMPT_CARDS: PromptCard[] = [
  { tag: "Sleep", tone: "grape", text: "How's my sleep been lately?" },
  { tag: "Patterns", tone: "sun", text: "What patterns do you see this week?" },
  { tag: "Care visit", tone: "sky", text: "Help me prepare for a doctor visit" },
];
// Used under a calm reply only when the backend sent no suggestions of its own. Safety-neutral on purpose.
const FOLLOW_UPS = ["Can you explain that more simply?", "What should I keep an eye on?", "Help me prepare questions for my clinician"];

/** A previous message that makes this reply a continuation of the same run (no second avatar). */
function isReplyInRun(prev: ChatMessage | undefined) {
  return prev?.role === "assistant" && !prev.retracted && !isUrgentMessage(prev);
}

function relativeDay(iso: unknown) {
  const date = typeof iso === "string" ? new Date(iso) : null;
  if (!date || Number.isNaN(date.getTime())) return "";
  const dayStart = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((dayStart(new Date()) - dayStart(date)) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days > 1 && days < 7) return date.toLocaleDateString(undefined, { weekday: "long" });
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function CompanionClient() {
  const router = useRouter();
  const { loading: authLoading, session } = useAuth();
  const { connectionError, fetchBubbles, checkApiHealth, apiStatus, reconnects } = useApi();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failed, setFailed] = useState<{ text: string; messageId: string; fresh?: boolean } | null>(null);
  const [history, setHistory] = useState<ConversationSummary[]>([]);
  const [historyState, setHistoryState] = useState<"loading" | "error" | "ready">("loading");
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [conversationError, setConversationError] = useState<string | null>(null);
  const [memoryLine, setMemoryLine] = useState("Checking memory…");
  const [eventStatus, setEventStatus] = useState<Record<string, EventStatus>>({});
  const [eventErrors, setEventErrors] = useState<Record<string, string>>({});
  const [consentBusy, setConsentBusy] = useState(false);
  const [ratings, setRatings] = useState<Record<string, Feedback>>({});
  const [ratingBusy, setRatingBusy] = useState<Record<string, boolean>>({});
  const [ratingFailed, setRatingFailed] = useState<Record<string, boolean>>({});
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("");

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const drawerRef = useRef<HTMLDialogElement>(null);
  const sendingRef = useRef(false);
  const refocusRef = useRef(false);
  // Bumped whenever the visible conversation changes, so late responses for the old one are dropped.
  const viewRef = useRef(0);

  useEffect(() => {
    if (!authLoading && !session) router.push("/login");
  }, [authLoading, session, router]);

  const loadHistory = useCallback(async () => {
    setHistoryState((s) => (s === "ready" ? s : "loading"));
    try {
      const response = await fetchBubbles("/chat/history?limit=20");
      if (!response.ok) throw new Error(`history ${response.status}`);
      const payload = await response.json();
      const rows: Array<{ id?: unknown; title?: unknown; created_at?: unknown; updated_at?: unknown }> = Array.isArray(payload?.conversations)
        ? payload.conversations
        : [];
      setHistory(
        rows
          .filter((c) => typeof c.id === "string")
          .map((c) => ({
            id: c.id as string,
            title: typeof c.title === "string" && c.title.trim() ? c.title : "Untitled conversation",
            when: relativeDay(c.updated_at ?? c.created_at),
          }))
      );
      setHistoryState("ready");
    } catch {
      setHistoryState("error");
    }
  }, [fetchBubbles]);

  useEffect(() => {
    if (session) void loadHistory();
  }, [session, loadHistory]);

  // Bubbles came back after being unreachable: reload the conversation list that failed while it was down.
  const seenReconnects = useRef(reconnects);
  useEffect(() => {
    if (seenReconnects.current === reconnects) return;
    seenReconnects.current = reconnects;
    if (session) void loadHistory();
  }, [reconnects, session, loadHistory]);

  useEffect(() => {
    if (!session) return;
    let live = true;
    fetchBubbles("/memory/diagnostics")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`memory ${r.status}`))))
      .then((payload) => {
        const memory = payload?.memory ?? {};
        const saved = (Number(memory.L2) || 0) + (Number(memory.L3) || 0);
        if (live) setMemoryLine(saved ? `Memory on · ${saved} ${saved === 1 ? "thing" : "things"} remembered` : "Memory on · nothing confirmed yet");
      })
      .catch(() => {
        if (live) setMemoryLine("Memory status unavailable right now");
      });
    return () => {
      live = false;
    };
  }, [session, fetchBubbles]);

  const sendMessage = useCallback(
    async (raw: string, retry?: { messageId: string; fresh?: boolean }) => {
      const text = raw.trim().slice(0, MAX_MESSAGE);
      if (!text || sendingRef.current) return;
      sendingRef.current = true;
      setSending(true);
      setError(null);
      setFailed(null);
      // Keep keyboard flow on desktop; don't pop the phone keyboard over Bubbles' reply.
      refocusRef.current = !window.matchMedia("(pointer: coarse)").matches;
      const freshId = `chat-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
      // Retrying inside a known conversation reuses the idempotency key. Without a conversation id the
      // backend would open a new conversation, and the old key would 409 there, so use a fresh one. A 409
      // (key reused for different text) also needs a fresh key.
      const messageId = retry && conversationId && !retry.fresh ? retry.messageId : freshId;
      const bubbleId = retry?.messageId ?? messageId;
      const view = viewRef.current;
      if (!retry) {
        setMessages((prev) => [...prev, { id: messageId, role: "user", content: text }]);
        setInput("");
      }

      let status: number | null = null;
      try {
        // Chat waits far longer than other calls and is never replayed on a timeout (see CHAT_TIMEOUT_MS).
        const response = await fetchBubbles(
          "/chat",
          {
            method: "POST",
            body: JSON.stringify({ conversation_id: conversationId, message: text, message_id: messageId }),
          },
          { timeoutMs: CHAT_TIMEOUT_MS, retries: 0 }
        );
        if (!response.ok) {
          status = response.status;
          throw new Error(`chat ${status}`);
        }
        const payload = await response.json();
        if (view !== viewRef.current) return;

        const safety = adaptReplySafety(payload?.safety, undefined, payload?.kind);
        const correction = adaptCorrection(payload?.safety?.correction);
        const reply: ChatMessage = {
          id: typeof payload?.message_id === "string" ? payload.message_id : `${messageId}-reply`,
          role: "assistant",
          content:
            typeof payload?.response === "string" && payload.response.trim()
              ? payload.response
              : "Bubbles didn't have a reply this time. Try asking again.",
          ...safety,
          evidence: adaptEvidence(payload?.evidence),
          confidence: confidenceLabel(typeof payload?.confidence === "number" ? payload.confidence : null),
          suggestions: Array.isArray(payload?.suggestions)
            ? [
                ...new Set<string>(
                  payload.suggestions.filter((s: unknown): s is string => typeof s === "string" && s.trim() !== "").map((s: string) => s.trim())
                ),
              ].slice(0, 4)
            : [],
          healthEvents: adaptHealthEvents(payload?.health_events, payload?.health_event_ids),
          consentRequired: payload?.consent_required === true,
        };
        // The user's bubble takes the server id; the correction (if any) withdraws the earlier warning in place;
        // the reply is upserted so a replayed response can never render twice.
        const userMessageId = typeof payload?.user_message_id === "string" ? payload.user_message_id : null;
        setMessages((prev) =>
          upsertById(applyCorrection(userMessageId ? replaceId(prev, bubbleId, userMessageId) : prev, correction), reply)
        );
        if (correction?.retractedEventIds.length) {
          setEventStatus((prev) => ({
            ...prev,
            ...Object.fromEntries(correction.retractedEventIds.map((id) => [id, "retracted" as const])),
          }));
        }
        // An urgent reply announces itself through its role="alert" banner.
        const spoken = safety.safetyLevel !== "RED" ? `Bubbles replied: ${reply.content.replace(/[*#]/g, "")}` : "";
        setAnnouncement(`${correction ? "Bubbles withdrew an earlier urgent warning. " : ""}${spoken}`.trim());
        if (!conversationId && typeof payload?.conversation_id === "string") {
          setConversationId(payload.conversation_id);
          void loadHistory();
        }
      } catch (caught) {
        if (view !== viewRef.current) return;
        setError(chatErrorMessage(status, isTimeoutError(caught)));
        setFailed({ text, messageId: bubbleId, fresh: needsFreshMessageId(status) });
        // The conversation is gone or invalid: forget it so "Try again" opens a new one instead of looping.
        if (resetsConversation(status)) setConversationId(undefined);
      } finally {
        sendingRef.current = false;
        setSending(false);
      }
    },
    [conversationId, fetchBubbles, loadHistory]
  );

  // Send the ?ask= question (or the one stored behind ?askref=, which keeps long health text out of the URL)
  // exactly once, then clear it from the URL. (sendMessage's identity changes after every send, so without
  // this guard the effect re-fired and re-sent the same question in a loop.)
  // Read from window.location rather than useSearchParams: the latter forces a client-render
  // bailout whose fallback then mismatches on hydration once auth has resolved.
  const handledAsk = useRef<string | null>(null);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const handle = askHandle(params);
    if (!handle || authLoading || !session || handledAsk.current === handle) return;
    handledAsk.current = handle;
    const question = readAsk(params);
    router.replace("/companion");
    if (question) void sendMessage(question);
  }, [authLoading, session, sendMessage, router]);

  const openConversation = useCallback(
    async (id: string) => {
      setDrawerOpen(false);
      if (id === conversationId && !conversationError) return;
      const view = ++viewRef.current;
      setConversationId(id);
      setMessages([]);
      setError(null);
      setFailed(null);
      setConversationError(null);
      setLoadingConversation(true);
      try {
        const response = await fetchBubbles(`/chat/conversations/${encodeURIComponent(id)}/messages?limit=100`);
        if (!response.ok) throw new Error(`messages ${response.status}`);
        const payload = await response.json();
        if (view !== viewRef.current) return;
        const rows: Array<{
          id?: unknown;
          role?: unknown;
          content?: unknown;
          safety?: unknown;
          safety_level?: unknown;
          kind?: unknown;
          health_events?: unknown;
          consent_required?: unknown;
        }> = Array.isArray(payload?.messages) ? payload.messages : [];
        setMessages(
          rows.map((m, i): ChatMessage => {
            const base = {
              id: typeof m.id === "string" ? m.id : `${id}-${i}`,
              content: typeof m.content === "string" ? m.content : "",
            };
            if (m.role === "user") return { ...base, role: "user" };
            // Reloaded history goes through the same adapters as a live reply, so a withdrawn warning stays withdrawn.
            return {
              ...base,
              role: "assistant",
              ...adaptReplySafety(m.safety, m.safety_level, m.kind),
              healthEvents: adaptHealthEvents(m.health_events, undefined),
              consentRequired: m.consent_required === true,
            };
          })
        );
        // Thumbs already given in this conversation (best effort: a failure just means no highlighted thumbs).
        const replyIds = rows.filter((m) => m.role !== "user" && typeof m.id === "string").map((m) => m.id as string);
        if (replyIds.length > 0) {
          try {
            const r = await fetchBubbles(ratingsPath(replyIds));
            if (r.ok) {
              const found = parseRatings(await r.json());
              if (view === viewRef.current) setRatings((prev) => ({ ...prev, ...found }));
            }
          } catch {
            /* ratings are optional */
          }
        }
      } catch {
        if (view === viewRef.current) setConversationError("Bubbles couldn't open this conversation.");
      } finally {
        if (view === viewRef.current) setLoadingConversation(false);
      }
    },
    [conversationId, conversationError, fetchBubbles]
  );

  function startNewConversation() {
    viewRef.current += 1;
    setConversationId(undefined);
    setMessages([]);
    setError(null);
    setFailed(null);
    setConversationError(null);
    setLoadingConversation(false);
    // From the drawer, the dialog hands focus back to its toggle; on desktop go straight to the composer.
    if (drawerOpen) setDrawerOpen(false);
    else inputRef.current?.focus();
  }

  /** The yes to using an outside AI model: saved on the server, then the question that was waiting is asked again. */
  const allowAi = useCallback(
    async (replyId: string) => {
      setConsentBusy(true);
      try {
        const response = await fetchBubbles("/me/consent", { method: "PUT", body: JSON.stringify({ ai_chat: true }) });
        if (!response.ok) throw new Error(`consent ${response.status}`);
        const at = messages.findIndex((m) => m.id === replyId);
        const asked = at > 0 ? messages[at - 1] : undefined;
        setMessages((prev) => prev.map((m) => (m.id === replyId ? { ...m, consentRequired: false } : m)));
        if (asked?.role === "user") await sendMessage(asked.content, { messageId: asked.id, fresh: true });
      } catch {
        setError("Bubbles couldn't save that just now. Please try again.");
      } finally {
        setConsentBusy(false);
      }
    },
    [fetchBubbles, messages, sendMessage]
  );

  const rateReply = useCallback(
    async (messageId: string, rating: Rating, reason?: FeedbackReason) => {
      setRatingBusy((prev) => ({ ...prev, [messageId]: true }));
      setRatingFailed((prev) => ({ ...prev, [messageId]: false }));
      try {
        const response = await fetchBubbles("/chat/feedback", {
          method: "POST",
          body: JSON.stringify({ message_id: messageId, rating, reason: reason ?? null }),
        });
        if (!response.ok) throw new Error(`feedback ${response.status}`);
        setRatings((prev) => ({ ...prev, [messageId]: { rating, reason: rating === "down" ? reason ?? null : null } }));
      } catch {
        setRatingFailed((prev) => ({ ...prev, [messageId]: true }));
      } finally {
        setRatingBusy((prev) => ({ ...prev, [messageId]: false }));
      }
    },
    [fetchBubbles]
  );

  const decideEvents = useCallback(
    async (messageId: string, ids: string[], confirmed: boolean) => {
      setEventStatus((prev) => ({ ...prev, ...Object.fromEntries(ids.map((id) => [id, "busy" as const])) }));
      setEventErrors((prev) => {
        const next = { ...prev };
        delete next[messageId];
        return next;
      });
      // 409/410: Bubbles withdrew this event after a correction, so it is settled rather than retryable.
      const results = await Promise.all(
        ids.map(async (id): Promise<"done" | "withdrawn" | "failed"> => {
          try {
            const response = await fetchBubbles(`/health-events/${encodeURIComponent(id)}/confirmation`, {
              method: "PATCH",
              body: JSON.stringify({ confirmed }),
            });
            if (response.ok) return "done";
            return response.status === 409 || response.status === 410 ? "withdrawn" : "failed";
          } catch {
            return "failed";
          }
        })
      );
      setEventStatus((prev) => {
        const next = { ...prev };
        results.forEach((r, i) => {
          if (r === "done") next[ids[i]] = confirmed ? "saved" : "dismissed";
          else if (r === "withdrawn") next[ids[i]] = "retracted";
          else delete next[ids[i]];
        });
        return next;
      });
      const failedCount = results.filter((r) => r === "failed").length;
      const withdrawnCount = results.filter((r) => r === "withdrawn").length;
      if (failedCount) {
        const which = failedCount < ids.length ? `${failedCount} of these` : ids.length === 1 ? "this" : "these";
        setEventErrors((prev) => ({
          ...prev,
          [messageId]: `Bubbles couldn't ${confirmed ? "save" : "discard"} ${which} just now. Nothing else changed. Try again.`,
        }));
      } else if (withdrawnCount) {
        setEventErrors((prev) => ({ ...prev, [messageId]: "Bubbles withdrew this after your correction, so it was not saved." }));
      }
    },
    [fetchBubbles]
  );

  // Auto-grow the composer up to ~8 lines.
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // An urgent reply (RED, URGENT or EMERGENCY, never a withdrawn one) must open on its alert banner, not scrolled past it.
    const last = messages.at(-1);
    const urgentBanner = last && isUrgentMessage(last) ? el.querySelector("li:last-of-type [role='alert']") : null;
    if (urgentBanner) urgentBanner.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
    else el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    if (!sending && refocusRef.current) {
      refocusRef.current = false;
      inputRef.current?.focus();
    }
  }, [sending]);

  useEffect(() => {
    const dialog = drawerRef.current;
    if (!dialog) return;
    if (drawerOpen && !dialog.open) dialog.showModal();
    else if (!drawerOpen && dialog.open) dialog.close();
  }, [drawerOpen]);

  if (authLoading || !session) {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-blush">
        <div role="status" className="flex flex-col items-center gap-4 text-center">
          <BubblesMascot size={80} mood="thinking" />
          <p className="m-0 text-body font-bold text-ink-soft">{authLoading ? "Loading Bubbles…" : "Taking you to sign in…"}</p>
        </div>
      </main>
    );
  }

  const lastReply = [...messages].reverse().find((m) => m.role === "assistant");
  const urgent = lastReply !== undefined && isUrgentMessage(lastReply);
  // Follow-up chips sit under the newest reply only, and only while nothing is in flight. Never under an urgent or
  // withdrawn reply. Backend suggestions win; the static set is only for a calm, ordinary reply.
  const tail = messages.at(-1);
  const calmTail = tail?.role === "assistant" && !sending && !isUrgentMessage(tail) && !tail.retracted && !tail.consentRequired ? tail : null;
  const chipsFor = calmTail?.id;
  const chips = !calmTail
    ? []
    : calmTail.suggestions?.length
      ? calmTail.suggestions.slice(0, 3)
      : calmTail.safetyLevel === "GREEN" && (calmTail.kind === undefined || calmTail.kind === "reply")
        ? FOLLOW_UPS
        : [];
  const composerDisabled = sending || loadingConversation || conversationError !== null;
  const nearLimit = input.length > MAX_MESSAGE - 1000;

  const conversationList = (
    <ConversationList
      items={history}
      state={historyState}
      activeId={conversationId}
      onSelect={(id) => void openConversation(id)}
      onNew={startNewConversation}
      onRetry={() => void loadHistory()}
    />
  );

  return (
    <main className="flex h-dvh flex-col overflow-hidden bg-blush">
      <ApiAlert connectionError={connectionError} onRetry={checkApiHealth} />

      <div className="flex min-h-0 flex-1">
        <Sidebar apiStatus={apiStatus} />

        <aside aria-label="Conversations" className="hidden w-[280px] shrink-0 flex-col overflow-y-auto border-r-2 border-line bg-surface px-4 py-6 lg:flex">
          {conversationList}
        </aside>

        <section aria-label="Chat with Bubbles" className="flex min-w-0 flex-1 flex-col">
          <header className="flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b-2 border-line bg-blush px-4 py-3 lg:px-7 lg:py-4">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setDrawerOpen(true)}
                aria-haspopup="dialog"
                aria-expanded={drawerOpen}
                aria-label="Your conversations"
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 border-line bg-surface text-ink lg:hidden"
              >
                <Icon d={ICONS.menu} size={20} />
              </button>
              {!urgent && <BubblesMascot size={44} />}
              <div className="min-w-0">
                <h1 className="m-0 font-display text-h3 font-semibold leading-tight text-ink lg:text-h2">Bubbles</h1>
                <p
                  className={`m-0 truncate text-[0.8125rem] font-extrabold ${
                    memoryLine.startsWith("Memory on") ? "text-bubbles-mint-deep" : "text-ink-soft"
                  }`}
                >
                  {memoryLine}
                </p>
              </div>
            </div>
            <p className="m-0 rounded-2xl border-2 border-line bg-surface px-3 py-1.5 text-[0.75rem] font-bold text-ink-soft sm:rounded-full sm:text-[0.8125rem]">
              Not a diagnosis · for emergencies call your local number
            </p>
          </header>

          <div ref={scrollerRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            <div className="mx-auto flex w-full max-w-[860px] flex-col px-4 py-6 lg:px-7">
              <h2 className="sr-only">Conversation</h2>
              {messages.length === 0 && !loadingConversation && !conversationError && !sending && (
                <div className="mx-auto flex w-full flex-col items-center gap-6 py-8 text-center">
                  <div className="bubbles-rise flex max-w-md flex-col items-center gap-3">
                    <BubblesMascot size={96} mood="happy" />
                    <p className="m-0 font-display text-h2 font-semibold text-ink">Hi, I&apos;m Bubbles</p>
                    <p className="m-0 text-body text-ink-soft">
                      Tell me how you&apos;re feeling or ask about your patterns. I connect what you share with your logs and trusted
                      sources. I can&apos;t diagnose, but I can help you understand and prepare.
                    </p>
                  </div>
                  <PromptCards cards={PROMPT_CARDS} disabled={composerDisabled} onPick={(text) => void sendMessage(text)} />
                </div>
              )}

              {loadingConversation && (
                <div role="status" aria-label="Loading conversation" className="flex flex-col gap-4">
                  <span className="bubbles-skeleton block h-14 w-3/5 self-end rounded-3xl" />
                  <span className="bubbles-skeleton block h-28 w-4/5 rounded-3xl" />
                  <span className="bubbles-skeleton block h-14 w-1/2 self-end rounded-3xl" />
                </div>
              )}

              {conversationError && (
                <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border-2 border-line bg-surface px-5 py-4">
                  <div className="flex items-center gap-3">
                    <BubblesMascot size={40} mood="resting" animated={false} />
                    <p className="m-0 text-body font-bold text-ink">{conversationError}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => conversationId && void openConversation(conversationId)}
                      className="bubbles-press min-h-[44px] rounded-full bg-bubbles-pink-ink px-5 text-body-sm font-extrabold text-white shadow-[0_4px_0_var(--bubbles-pink-deep)]"
                    >
                      Try again
                    </button>
                    <button type="button" onClick={startNewConversation} className="min-h-[44px] rounded-full border-2 border-ink bg-surface px-5 text-body-sm font-extrabold">
                      New conversation
                    </button>
                  </div>
                </div>
              )}

              <ol aria-label="Messages" className="m-0 flex list-none flex-col gap-[18px] p-0">
                {messages.map((m, i) =>
                  m.role === "user" ? (
                    <li key={m.clientId ?? m.id} className="bubbles-rise flex max-w-[85%] flex-col items-end gap-1 self-end sm:max-w-[min(72%,34rem)]">
                      <p data-private className="m-0 whitespace-pre-wrap break-words rounded-[22px_22px_8px_22px] bg-bubbles-pink-ink px-[18px] py-3.5 shadow-[0_3px_0_var(--bubbles-pink-deep)] text-body font-semibold leading-normal text-white">
                        <span className="sr-only">You: </span>
                        {m.content}
                      </p>
                      {failed?.messageId === m.id && <span className="text-[0.8125rem] font-bold text-bubbles-urgent">Bubbles didn&apos;t reply to this yet</span>}
                    </li>
                  ) : (
                    <BubblesReply
                      key={m.id}
                      message={m}
                      eventStatus={eventStatus}
                      eventError={eventErrors[m.id]}
                      onDecide={(ids, confirmed) => void decideEvents(m.id, ids, confirmed)}
                      showAvatar={!isReplyInRun(messages[i - 1])}
                      chips={m.id === chipsFor ? chips : undefined}
                      onChip={(text) => void sendMessage(text)}
                      chipsDisabled={composerDisabled}
                      feedback={ratings[m.id]}
                      feedbackBusy={ratingBusy[m.id] === true}
                      feedbackFailed={ratingFailed[m.id] === true}
                      onRate={(rating, reason) => void rateReply(m.id, rating, reason)}
                      onConsent={m.id === messages.at(-1)?.id ? () => void allowAi(m.id) : undefined}
                      consentBusy={consentBusy}
                    />
                  )
                )}
                {sending && <ThinkingBubble />}
              </ol>
            </div>
          </div>
          <p className="sr-only" aria-live="polite">
            {announcement}
          </p>

          <div className="shrink-0 border-t-2 border-line bg-blush px-4 pb-3 pt-3 lg:px-7 lg:pb-5">
            <div className="mx-auto flex w-full max-w-[860px] flex-col gap-2.5">
              {error && (
                <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border-2 border-bubbles-urgent/30 bg-tint-urgent px-4 py-2.5">
                  <p className="m-0 text-body-sm font-bold text-bubbles-urgent">{error}</p>
                  {failed && (
                    <button
                      type="button"
                      onClick={() => void sendMessage(failed.text, { messageId: failed.messageId, fresh: failed.fresh })}
                      className="min-h-[44px] rounded-full border-2 border-ink bg-surface px-4 text-body-sm font-extrabold text-ink"
                    >
                      Try again
                    </button>
                  )}
                </div>
              )}

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void sendMessage(input);
                }}
                className="flex flex-col gap-1.5"
              >
                <div className="flex items-baseline justify-between gap-3 px-1">
                  <label htmlFor="bubbles-message" className="text-body-sm font-extrabold text-ink">
                    Message Bubbles
                  </label>
                  <span id="bubbles-message-hint" className={`text-[0.8125rem] font-semibold ${nearLimit ? "text-bubbles-urgent" : "text-ink-soft"}`}>
                    {nearLimit ? (
                      `${input.length.toLocaleString()} / ${MAX_MESSAGE.toLocaleString()} characters`
                    ) : (
                      <span className="hidden sm:inline">Enter to send · Shift+Enter for a new line</span>
                    )}
                  </span>
                </div>
                <div className="flex items-end gap-2.5 rounded-[28px] border-2 border-ink bg-surface py-1.5 pl-5 pr-1.5 shadow-[0_5px_0_var(--bubbles-ink)] transition-colors focus-within:border-bubbles-grape focus-within:shadow-[0_5px_0_var(--bubbles-grape)]">
                  <textarea
                    id="bubbles-message"
                    ref={inputRef}
                    rows={1}
                    value={input}
                    maxLength={MAX_MESSAGE}
                    disabled={composerDisabled}
                    aria-describedby="bubbles-message-hint"
                    placeholder="Tell Bubbles how you're feeling…"
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                        e.preventDefault();
                        void sendMessage(input);
                      }
                    }}
                    className="max-h-[200px] min-h-[44px] min-w-0 flex-1 resize-none border-0 bg-transparent py-2.5 text-body text-ink outline-none focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-70"
                  />
                  <button
                    type="submit"
                    aria-label={sending ? "Sending" : "Send message"}
                    aria-busy={sending}
                    disabled={composerDisabled || !input.trim()}
                    className={`bubbles-press flex h-12 w-12 shrink-0 items-center justify-center rounded-full disabled:cursor-not-allowed ${
                      sending || input.trim()
                        ? "bg-bubbles-pink-ink text-white shadow-[0_4px_0_var(--bubbles-pink-deep)]"
                        : "bg-tint-pink text-bubbles-pink-deep shadow-none"
                    }`}
                  >
                    {sending ? (
                      <svg viewBox="0 0 24 24" width={22} height={22} fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" aria-hidden="true" className="motion-safe:animate-spin">
                        <path d="M12 3a9 9 0 1 0 9 9" />
                      </svg>
                    ) : (
                      <Icon d={ICONS.send} size={22} strokeWidth={2.6} />
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </section>
      </div>

      <MobileNav />

      <dialog
        ref={drawerRef}
        aria-label="Your conversations"
        onClose={() => setDrawerOpen(false)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setDrawerOpen(false);
        }}
        className="m-0 h-dvh max-h-none w-[min(320px,86vw)] max-w-none border-0 bg-surface p-0 backdrop:bg-ink/40"
      >
        {drawerOpen && (
          <div className="bubbles-rise flex h-full flex-col gap-3 overflow-y-auto p-4">
            <div className="flex items-center justify-between">
              <h2 className="m-0 font-display text-h3 font-semibold">Conversations</h2>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                aria-label="Close conversations"
                className="flex h-11 w-11 items-center justify-center rounded-full border-2 border-line text-ink"
              >
                <Icon d={ICONS.close} size={20} />
              </button>
            </div>
            {conversationList}
          </div>
        )}
      </dialog>
    </main>
  );
}
