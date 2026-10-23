"use client";

import { Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Sidebar, MobileNav, ApiAlert } from "../../components/Navigation";
import { useAuth, useApi } from "../../components/Providers";
import { BubblesMascot } from "../../components/BubblesMascot";
import { LoadingBubbles } from "../../components/hub/HubKit";
import { supabase } from "../../lib/supabase";
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
import { readAsk } from "../lib/ask-handoff";
import { adaptHarbor } from "../lib/safe-harbor";
import { chatErrorMessage, isTimeoutError, needsFreshMessageId, resetsConversation } from "../lib/chat-flow";
import { clearDecline, readDecline, writeDecline } from "./decline";
import {
  applyOptimistic,
  decisionError,
  isAmbiguous,
  markChecking,
  markRetracted,
  rollback,
  settleFromRead,
  settleFromServer,
  statusesFromRows,
  submitDecisions,
  type Decisions,
} from "./event-decisions";
import { parseRatings, ratingsPath, type Feedback, type FeedbackReason, type Rating } from "./feedback";
import { continuingLabel, mapMessageRows, olderCursor, parseEntry, pickLatest, prependOlder, scrollPlan } from "./resume";
import { ChatHttpError, emptyStream, loaderCalm, requestChat, showPartial, type StreamView } from "./stream";
import {
  BubblesReply,
  ConversationList,
  Icon,
  ICONS,
  PartialReply,
  PromptCards,
  ThinkingBubble,
  type ChatMessage,
  type ConversationSummary,
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
const DECLINE_REPLY = "No problem. I won't send anything to an outside AI model. You can turn it on any time in Settings.";

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

const isTouch = () => typeof window !== "undefined" && window.matchMedia("(pointer: coarse)").matches;

/** Reports the URL's query string (a plain /companion link, ?new=1, ?ask=) so a link to this same page is noticed too. */
function SearchWatcher({ onChange }: { onChange: (search: string) => void }) {
  const search = useSearchParams().toString();
  useEffect(() => {
    onChange(search);
  }, [search, onChange]);
  return null;
}

/** Heart-to-heart (Orbit) opens as a blank thread of its own, in the dusk theme, and tells the server so with `mode: "orbit"`. */
/** A chip the server sends under relationship talk in Talk: it opens Heart-to-heart instead of sending a message. */
const OPEN_ORBIT = "Open in Heart-to-heart";
const ORBIT_STARTERS = ["We had a fight and I don't know how to start fixing it", "I don't know what to say to them", "I'm feeling distant from someone I love", "Help me understand something they said"];

export function CompanionClient({ mode = "talk" }: { mode?: "talk" | "orbit" } = {}) {
  const router = useRouter();
  const { loading: authLoading, session } = useAuth();
  const { connectionError, fetchBubbles, checkApiHealth, apiStatus, reconnects } = useApi();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [stream, setStream] = useState<StreamView>(emptyStream);
  const [error, setError] = useState<string | null>(null);
  const [failed, setFailed] = useState<{ text: string; messageId: string; fresh?: boolean } | null>(null);
  const [history, setHistory] = useState<ConversationSummary[]>([]);
  // A past Heart-to-heart opened from the Talk history keeps its voice: its replies are sent as `mode: "orbit"`.
  const [threadMode, setThreadMode] = useState<"talk" | "orbit">("talk");
  const [historyState, setHistoryState] = useState<"loading" | "error" | "ready">("loading");
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [conversationError, setConversationError] = useState<string | null>(null);
  /** Opening the latest chat on arrival: loading until the answer is in, error when it could not be read. */
  const [resumeState, setResumeState] = useState<"loading" | "ready" | "error">("loading");
  const [hasMore, setHasMore] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [olderFailed, setOlderFailed] = useState(false);
  const [continuing, setContinuing] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Decisions>({});
  const [eventErrors, setEventErrors] = useState<Record<string, string>>({});
  const [consentBusy, setConsentBusy] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [ratings, setRatings] = useState<Record<string, Feedback>>({});
  const [ratingBusy, setRatingBusy] = useState<Record<string, boolean>>({});
  const [ratingFailed, setRatingFailed] = useState<Record<string, boolean>>({});
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [urlSearch, setUrlSearch] = useState<string | null>(null);
  const [askTick, setAskTick] = useState(0);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const drawerRef = useRef<HTMLDialogElement>(null);
  const sendingRef = useRef(false);
  const refocusRef = useRef(false);
  // Bumped whenever the visible conversation changes, so late responses for the old one are dropped.
  const viewRef = useRef(0);
  const decisionsRef = useRef<Decisions>({});
  const conversationIdRef = useRef<string | undefined>(undefined);
  const historyWanted = useRef(false);
  // A question handed over by ?ask= / ?askref=, held until the latest chat is open so it lands in that chat.
  const pendingAsk = useRef<string | null>(null);
  const handledAsk = useRef<string | null>(null);
  const lastSearch = useRef<string | null>(null);
  // Scroll bookkeeping (see scrollPlan): a chat was just opened, older rows were added on top, what the last row was.
  const openedRef = useRef(false);
  const anchorRef = useRef<{ height: number; top: number } | null>(null);
  const lastKeyRef = useRef<string | null>(null);
  const wasSendingRef = useRef(false);

  useEffect(() => {
    decisionsRef.current = decisions;
  }, [decisions]);
  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);
  useEffect(() => {
    setDeclined(readDecline());
  }, []);

  useEffect(() => {
    if (!authLoading && !session) router.push("/login");
  }, [authLoading, session, router]);

  const loadHistory = useCallback(async () => {
    historyWanted.current = true;
    setHistoryState((s) => (s === "ready" ? s : "loading"));
    try {
      const response = await fetchBubbles("/chat/history?limit=20");
      if (!response.ok) throw new Error(`history ${response.status}`);
      const payload = await response.json();
      if (payload?.degraded === true) throw new Error("history degraded");
      const rows: Array<{ id?: unknown; title?: unknown; created_at?: unknown; updated_at?: unknown; mode?: unknown }> = Array.isArray(payload?.conversations)
        ? payload.conversations
        : [];
      setHistory(
        rows
          .filter((c) => typeof c.id === "string")
          .map((c) => ({
            id: c.id as string,
            title: typeof c.title === "string" && c.title.trim() ? c.title : "Untitled chat",
            when: relativeDay(c.updated_at ?? c.created_at),
            mode: c.mode === "orbit" ? ("orbit" as const) : ("talk" as const),
          }))
      );
      setHistoryState("ready");
    } catch {
      setHistoryState("error");
    }
  }, [fetchBubbles]);

  // The list is only fetched when it can be seen: always visible on a wide screen, on demand behind History on a phone.
  useEffect(() => {
    if (mode !== "orbit" && session && window.matchMedia("(min-width: 1024px)").matches) void loadHistory();
  }, [mode, session, loadHistory]);

  // Bubbles came back after being unreachable: reload the list that failed while it was down.
  const seenReconnects = useRef(reconnects);
  useEffect(() => {
    if (seenReconnects.current === reconnects) return;
    seenReconnects.current = reconnects;
    if (session && historyWanted.current) void loadHistory();
  }, [reconnects, session, loadHistory]);

  const openHistory = useCallback(() => {
    if (!historyWanted.current || historyState === "error") void loadHistory();
    setDrawerOpen(true);
  }, [historyState, loadHistory]);

  const refreshToken = useCallback(async () => {
    const { data } = await supabase.auth.refreshSession();
    return data.session?.access_token ?? null;
  }, []);

  const sendMessage = useCallback(
    async (raw: string, retry?: { messageId: string; fresh?: boolean }) => {
      const text = raw.trim().slice(0, MAX_MESSAGE);
      if (!text || sendingRef.current) return;
      sendingRef.current = true;
      setSending(true);
      setError(null);
      setFailed(null);
      setStream(emptyStream);
      // Keep keyboard flow on desktop; don't pop the phone keyboard over Bubbles' reply.
      refocusRef.current = !isTouch();
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
        // Words arrive on the stream when the server has one; any trouble falls back to plain POST /chat (see stream.ts).
        const { payload } = await requestChat({
          fetcher: fetchBubbles,
          body: JSON.stringify({ conversation_id: conversationId, message: text, message_id: messageId, ...(mode === "orbit" || threadMode === "orbit" ? { mode: "orbit" } : {}) }),
          onMeta: (meta) => {
            if (view === viewRef.current) setStream((prev) => ({ ...prev, meta }));
          },
          onDelta: (piece) => {
            if (view === viewRef.current) setStream((prev) => ({ ...prev, text: prev.text + piece }));
          },
        });
        if (view !== viewRef.current) return;
        const body = payload as Record<string, unknown>;

        const safety = adaptReplySafety(body?.safety, undefined, body?.kind);
        const correction = adaptCorrection((body?.safety as { correction?: unknown } | undefined)?.correction);
        const reply: ChatMessage = {
          id: typeof body?.message_id === "string" ? body.message_id : `${messageId}-reply`,
          role: "assistant",
          content:
            typeof body?.response === "string" && body.response.trim()
              ? body.response
              : "Bubbles didn't have a reply this time. Try asking again.",
          ...safety,
          evidence: adaptEvidence(body?.evidence),
          confidence: confidenceLabel(typeof body?.confidence === "number" ? body.confidence : null),
          suggestions: Array.isArray(body?.suggestions)
            ? [
                ...new Set<string>(
                  body.suggestions.filter((s: unknown): s is string => typeof s === "string" && s.trim() !== "").map((s: string) => s.trim())
                ),
              ].slice(0, 4)
            : [],
          healthEvents: adaptHealthEvents(body?.health_events, body?.health_event_ids),
          consentRequired: body?.consent_required === true && body?.consent_ask !== false, // a recent "No" gets a calm line, not the card again
          harbor: adaptHarbor(body?.harbor) ?? undefined,
        };
        // The user's bubble takes the server id; the correction (if any) withdraws the earlier warning in place;
        // the reply is upserted so a replayed response can never render twice.
        const userMessageId = typeof body?.user_message_id === "string" ? body.user_message_id : null;
        setMessages((prev) =>
          upsertById(applyCorrection(userMessageId ? replaceId(prev, bubbleId, userMessageId) : prev, correction), reply)
        );
        if (correction?.retractedEventIds.length) setDecisions((prev) => markRetracted(prev, correction.retractedEventIds));
        // An urgent reply announces itself through its role="alert" banner.
        const spoken = safety.safetyLevel !== "RED" ? `Bubbles replied: ${reply.content.replace(/[*#]/g, "")}` : "";
        setAnnouncement(`${correction ? "Bubbles withdrew an earlier urgent warning. " : ""}${spoken}`.trim());
        if (!conversationId && typeof body?.conversation_id === "string") {
          setConversationId(body.conversation_id);
          if (historyWanted.current) void loadHistory();
        }
      } catch (caught) {
        if (view !== viewRef.current) return;
        status = caught instanceof ChatHttpError ? caught.status : null;
        setError(chatErrorMessage(status, isTimeoutError(caught)));
        setFailed({ text, messageId: bubbleId, fresh: needsFreshMessageId(status) });
        // The conversation is gone or invalid: forget it so "Try again" opens a new one instead of looping.
        if (resetsConversation(status)) setConversationId(undefined);
      } finally {
        sendingRef.current = false;
        setSending(false);
        setStream(emptyStream);
      }
    },
    [conversationId, fetchBubbles, loadHistory, mode, threadMode]
  );

  /** Best effort: thumbs already given in this conversation. A failure just means no highlighted thumbs. */
  const loadRatings = useCallback(
    async (rows: ChatMessage[], view: number) => {
      const replyIds = rows.filter((m) => m.role !== "user").map((m) => m.id);
      if (replyIds.length === 0) return;
      try {
        const r = await fetchBubbles(ratingsPath(replyIds));
        if (r.ok) {
          const found = parseRatings(await r.json());
          if (view === viewRef.current) setRatings((prev) => ({ ...prev, ...found }));
        }
      } catch {
        /* ratings are optional */
      }
    },
    [fetchBubbles]
  );

  /** Show one stored conversation. Returns whether it opened; `view` guards against a newer navigation. */
  const showConversation = useCallback(
    async (id: string, view: number, announceDay: boolean): Promise<boolean> => {
      const response = await fetchBubbles(`/chat/conversations/${encodeURIComponent(id)}/messages?limit=100`);
      if (!response.ok) throw new Error(`messages ${response.status}`);
      const payload = await response.json();
      if (view !== viewRef.current) return true;
      const rows = mapMessageRows(payload?.messages, id);
      openedRef.current = true;
      setMessages(rows);
      setHasMore(payload?.has_more === true);
      setContinuing(announceDay ? continuingLabel(rows.at(-1)?.createdAt) : null);
      void loadRatings(rows, view);
      return true;
    },
    [fetchBubbles, loadRatings]
  );

  const clearThread = useCallback(() => {
    setMessages([]);
    setError(null);
    setFailed(null);
    setConversationError(null);
    setHasMore(false);
    setOlderFailed(false);
    setContinuing(null);
    setStream(emptyStream);
  }, []);

  const openConversation = useCallback(
    async (id: string) => {
      setDrawerOpen(false);
      if (id === conversationId && !conversationError) return;
      const view = ++viewRef.current;
      setConversationId(id);
      clearThread();
      setLoadingConversation(true);
      try {
        await showConversation(id, view, false);
      } catch {
        if (view === viewRef.current) setConversationError("Bubbles couldn't open this chat.");
      } finally {
        if (view === viewRef.current) setLoadingConversation(false);
      }
    },
    [conversationId, conversationError, clearThread, showConversation]
  );

  const startNewChat = useCallback(() => {
    viewRef.current += 1;
    setConversationId(undefined);
    setThreadMode("talk");
    clearThread();
    setLoadingConversation(false);
    setResumeState("ready");
    // From the drawer, the dialog hands focus back to its toggle; on a computer go straight to the composer.
    if (drawerRef.current?.open) setDrawerOpen(false);
    else if (!isTouch()) inputRef.current?.focus();
  }, [clearThread]);

  /** Open the latest chat that has a message in it. Falls back to the history list when the server has no /chat/latest yet. */
  const resume = useCallback(async () => {
    const view = ++viewRef.current;
    setResumeState("loading");
    setConversationId(undefined);
    clearThread();
    try {
      const response = await fetchBubbles("/chat/latest?limit=100");
      if (response.status === 404 || response.status === 405) {
        const list = await fetchBubbles("/chat/history?limit=10");
        if (!list.ok) throw new Error(`history ${list.status}`);
        const payload = await list.json();
        if (payload?.degraded === true) throw new Error("history degraded");
        const rows: Array<{ id?: unknown; message_count?: unknown }> = Array.isArray(payload?.conversations) ? payload.conversations : [];
        const pick = rows.find((c) => typeof c.id === "string" && (typeof c.message_count !== "number" || c.message_count > 0));
        if (view !== viewRef.current) return;
        if (pick) {
          setConversationId(pick.id as string);
          await showConversation(pick.id as string, view, true);
        }
        if (view === viewRef.current) setResumeState("ready");
        return;
      }
      if (!response.ok) throw new Error(`latest ${response.status}`);
      const latest = pickLatest(await response.json());
      if (view !== viewRef.current) return;
      if (latest.kind === "error") throw new Error("latest unreadable");
      if (latest.kind === "chat") {
        openedRef.current = true;
        setConversationId(latest.conversationId);
        setMessages(latest.messages);
        setHasMore(latest.hasMore);
        setContinuing(continuingLabel(latest.messages.at(-1)?.createdAt));
        void loadRatings(latest.messages, view);
      }
      setResumeState("ready");
    } catch {
      if (view === viewRef.current) setResumeState("error");
    }
  }, [fetchBubbles, clearThread, showConversation, loadRatings]);

  // The URL decides how Talk opens: a plain link resumes the latest chat, ?new=1 starts a blank one, and ?ask= / ?askref=
  // carries a question that is sent into whichever chat ends up open. Read from the URL by SearchWatcher so a link to
  // this same page (the palette's "New chat") is noticed without a remount.
  const firstEntry = useRef(true);
  useEffect(() => {
    if (urlSearch === null || authLoading || !session || lastSearch.current === urlSearch) return;
    lastSearch.current = urlSearch;
    const params = new URLSearchParams(urlSearch);
    const entry = parseEntry(params);
    if (entry.ask && handledAsk.current !== entry.ask) {
      handledAsk.current = entry.ask;
      pendingAsk.current = readAsk(params);
      setAskTick((n) => n + 1);
    }
    const first = firstEntry.current;
    firstEntry.current = false;
    if (entry.fresh) startNewChat();
    else if (first) {
      if (mode === "orbit") startNewChat();
      else void resume();
    }
    if (entry.fresh || entry.ask) router.replace(mode === "orbit" ? "/orbit/talk" : "/companion");
  }, [mode, urlSearch, authLoading, session, router, resume, startNewChat]);

  // Once the chat is open and idle, send the question that was waiting.
  useEffect(() => {
    if (resumeState !== "ready" || sending || loadingConversation || !pendingAsk.current) return;
    const question = pendingAsk.current;
    pendingAsk.current = null;
    void sendMessage(question);
  }, [resumeState, askTick, sending, loadingConversation, sendMessage]);

  const loadOlder = useCallback(async () => {
    const id = conversationIdRef.current;
    const cursor = olderCursor(messages);
    if (!id || !cursor || loadingOlder) return;
    const view = viewRef.current;
    setLoadingOlder(true);
    setOlderFailed(false);
    try {
      const response = await fetchBubbles(`/chat/conversations/${encodeURIComponent(id)}/messages?limit=100&before=${encodeURIComponent(cursor)}`);
      if (!response.ok) throw new Error(`older ${response.status}`);
      const payload = await response.json();
      if (view !== viewRef.current) return;
      const el = scrollerRef.current;
      if (el) anchorRef.current = { height: el.scrollHeight, top: el.scrollTop };
      setMessages((prev) => prependOlder(prev, mapMessageRows(payload?.messages, id)));
      setHasMore(payload?.has_more === true);
    } catch {
      if (view === viewRef.current) setOlderFailed(true);
    } finally {
      setLoadingOlder(false);
    }
  }, [messages, loadingOlder, fetchBubbles]);

  /** The yes to using an outside AI model: saved on the server, then the question that was waiting is asked again. */
  const allowAi = useCallback(
    async (replyId: string) => {
      setConsentBusy(true);
      try {
        const response = await fetchBubbles("/me/consent", { method: "PUT", body: JSON.stringify({ ai_chat: true, source: "chat_card" }) });
        if (!response.ok) throw new Error(`consent ${response.status}`);
        clearDecline();
        setDeclined(false);
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

  /**
   * The no: recorded on the server when it can be (PUT /consents/ai_chat_processing), and always remembered here, so
   * a server that does not have that route yet still gets a calm, working "No". Nothing is sent to a model either way.
   */
  const declineAi = useCallback(
    async (replyId: string) => {
      setConsentBusy(true);
      try {
        await fetchBubbles("/consents/ai_chat_processing", {
          method: "PUT",
          body: JSON.stringify({ granted: false, source: "chat_card", text_hash: null }),
        });
      } catch {
        // offline or not built yet: the decline still holds on this device
      }
      writeDecline();
      setDeclined(true);
      setMessages((prev) => [
        ...prev.map((m) => (m.id === replyId ? { ...m, consentRequired: false } : m)),
        { id: `local-decline-${Date.now().toString(36)}`, role: "assistant", content: DECLINE_REPLY, safetyLevel: "GREEN", kind: "reply" },
      ]);
      setConsentBusy(false);
    },
    [fetchBubbles]
  );

  const reconsiderAi = useCallback(() => {
    clearDecline();
    setDeclined(false);
  }, []);

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

  /** After an answer was lost: read what the server really stored instead of assuming the save failed. */
  const readSettled = useCallback(async (): Promise<Record<string, string> | null> => {
    const id = conversationIdRef.current;
    if (!id) return null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const response = await fetchBubbles(`/chat/conversations/${encodeURIComponent(id)}/messages?limit=100`, {}, { timeoutMs: 15000, retries: 1 });
        if (response.ok) return statusesFromRows((await response.json())?.messages);
      } catch {
        // try once more below
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1500));
    }
    return null;
  }, [fetchBubbles]);

  const decideEvents = useCallback(
    async (messageId: string, ids: string[], confirmed: boolean) => {
      // A second press on something already decided is harmless: only ids without a decision go out.
      const fresh = ids.filter((id) => !decisionsRef.current[id]);
      if (fresh.length === 0) return;
      setDecisions((prev) => applyOptimistic(prev, fresh, confirmed));
      setEventErrors((prev) => {
        const next = { ...prev };
        delete next[messageId];
        return next;
      });

      const sent = await submitDecisions(fetchBubbles, fresh, confirmed, refreshToken);
      const answered = fresh.filter((id) => !sent.unanswered.includes(id));
      const settled = settleFromServer(decisionsRef.current, sent.results, answered, confirmed);
      setDecisions((prev) => settleFromServer(prev, sent.results, answered, confirmed).state);

      let failedIds = sent.unanswered;
      let refusal = sent.status;
      if (sent.unanswered.length > 0) {
        if (isAmbiguous(sent.status)) {
          // Timeout, dropped connection or a waking host: the server may have committed. Say so and look.
          setDecisions((prev) => markChecking(prev, sent.unanswered));
          const statuses = await readSettled();
          const read = settleFromRead(decisionsRef.current, sent.unanswered, statuses ?? {});
          setDecisions((prev) => settleFromRead(prev, sent.unanswered, statuses ?? {}).state);
          failedIds = read.missing;
          refusal = null;
        } else {
          setDecisions((prev) => rollback(prev, sent.unanswered));
        }
      }

      const message =
        decisionError(confirmed, failedIds.length, fresh.length, refusal) ??
        (settled.withdrawn.length ? "Bubbles withdrew this after your correction, so it was not saved." : null) ??
        (settled.differed.length ? "That was already saved, so it stays saved." : null);
      if (message) setEventErrors((prev) => ({ ...prev, [messageId]: message }));
    },
    [fetchBubbles, refreshToken, readSettled]
  );

  // Auto-grow the composer up to ~8 lines.
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  // Where the list should be after it changed. Before paint, so an opened chat never flashes at the top.
  useLayoutEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const last = messages.at(-1);
    const key = last ? (last.clientId ?? last.id) : null;
    const plan = scrollPlan({
      opened: openedRef.current,
      prepended: anchorRef.current !== null,
      lastIdChanged: key !== lastKeyRef.current,
      sendingStarted: sending && !wasSendingRef.current,
    });
    lastKeyRef.current = key;
    wasSendingRef.current = sending;
    if (plan === "none") return;
    if (plan === "anchor") {
      const anchor = anchorRef.current;
      anchorRef.current = null;
      if (anchor) el.scrollTop = anchor.top + (el.scrollHeight - anchor.height);
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const behavior: ScrollBehavior = plan === "jump" || reduce ? "auto" : "smooth";
    if (plan === "jump") openedRef.current = false;
    // An urgent reply (RED, URGENT or EMERGENCY, never a withdrawn one) must open on its alert banner, not scrolled past it.
    const urgentBanner = last && isUrgentMessage(last) ? el.querySelector("li:last-of-type [role='alert']") : null;
    if (urgentBanner) urgentBanner.scrollIntoView({ block: "start", behavior });
    else el.scrollTo({ top: el.scrollHeight, behavior });
  }, [messages, sending]);

  // Words arriving on the stream: stay at the bottom, but only if the reader is already there.
  useLayoutEffect(() => {
    const el = scrollerRef.current;
    if (el && stream.text && el.scrollHeight - el.scrollTop - el.clientHeight < 160) el.scrollTop = el.scrollHeight;
  }, [stream.text]);

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
        <LoadingBubbles label={authLoading ? "Loading Bubbles…" : "Taking you to sign in…"} />
      </main>
    );
  }

  const lastReply = [...messages].reverse().find((m) => m.role === "assistant");
  const urgent = lastReply !== undefined && isUrgentMessage(lastReply);
  // Caution replies hide the header mascot too: no mascot near a safety banner.
  const caution = lastReply?.safetyLevel === "AMBER" && !lastReply.retracted;
  const harborVoice = lastReply?.harbor !== undefined; // the Safe Harbor voice has no mascot, in the header or while it is thinking
  // Follow-up chips sit under the newest reply only, and only while nothing is in flight. Never under an urgent or
  // withdrawn reply. Backend suggestions win; the static set is only for a calm, ordinary reply.
  const tail = messages.at(-1);
  const calmTail = tail?.role === "assistant" && !sending && !isUrgentMessage(tail) && !tail.retracted && !tail.consentRequired ? tail : null;
  const chipsFor = calmTail?.id;
  const chips = !calmTail
    ? []
    : calmTail.harbor
      ? calmTail.harbor.actions.map((a) => a.label) // Safe Harbor: only its own choices, never the ordinary follow-ups
      : calmTail.suggestions?.length
      ? calmTail.suggestions.slice(0, 3)
      : calmTail.safetyLevel === "GREEN" && (calmTail.kind === undefined || calmTail.kind === "reply")
        ? FOLLOW_UPS
        : [];
  const resuming = resumeState === "loading";
  const composerDisabled = sending || loadingConversation || conversationError !== null || resumeState !== "ready";
  const nearLimit = input.length > MAX_MESSAGE - 1000;
  const loadProblem = resumeState === "error" ? "Bubbles couldn't open your latest chat." : conversationError;
  const retryLoad = () => {
    if (resumeState === "error") void resume();
    else if (conversationId) void openConversation(conversationId);
  };
  const partial = sending && showPartial(stream);

  const conversationList = (inDrawer: boolean) => (
    <ConversationList
      items={history}
      state={historyState}
      activeId={conversationId}
      onSelect={(id) => { setThreadMode(history.find((c) => c.id === id)?.mode === "orbit" ? "orbit" : "talk"); void openConversation(id); }}
      onNew={startNewChat}
      onRetry={() => void loadHistory()}
      heading={!inDrawer}
    />
  );

  const headerButton =
    "bubbles-press inline-flex min-h-[44px] items-center gap-1.5 rounded-full border border-line bg-surface px-3.5 text-body-sm font-extrabold text-ink";

  return (
    <main className={`${mode === "orbit" ? "dusk " : ""}flex h-dvh flex-col overflow-hidden bg-blush`}>
      <Suspense fallback={null}>
        <SearchWatcher onChange={setUrlSearch} />
      </Suspense>
      <ApiAlert connectionError={connectionError} onRetry={checkApiHealth} />

      <div className="flex min-h-0 flex-1">
        <Sidebar apiStatus={apiStatus} />

        <aside aria-label="History" className={`${mode === "orbit" ? "hidden" : "hidden lg:flex"} w-[280px] shrink-0 flex-col overflow-y-auto border-r border-[color:var(--hairline)] bg-surface px-4 py-6`}>
          {conversationList(false)}
        </aside>

        <section aria-label="Chat with Bubbles" className="flex min-w-0 flex-1 flex-col">
          <header className="flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-[color:var(--hairline)] bg-blush px-4 py-3 lg:px-7 lg:py-4">
            <div className="flex min-w-0 items-center gap-3">
              {!urgent && !caution && !harborVoice && mode !== "orbit" && <BubblesMascot size={44} animated={false} />}
              <h1 className="m-0 font-display text-h3 font-semibold leading-tight text-ink lg:text-h2">{mode === "orbit" ? "Heart-to-heart" : "Bubbles"}</h1>
            </div>
            <div className="flex items-center gap-2">
              {mode === "orbit" ? (
                <>
                  <Link href="/orbit" className={`${headerButton} no-underline`}>
                    Orbit
                  </Link>
                  <button type="button" onClick={() => router.replace("/dashboard")} className={headerButton}>
                    Hide
                  </button>
                </>
              ) : (
                <button type="button" onClick={openHistory} aria-haspopup="dialog" aria-expanded={drawerOpen} className={headerButton}>
                  <Icon d={ICONS.menu} size={18} />
                  History
                </button>
              )}
              <button type="button" onClick={startNewChat} className={`${headerButton} border-bubbles-pink-ink text-bubbles-pink-ink`}>
                <Icon d={ICONS.plus} size={18} strokeWidth={2.6} />
                New chat
              </button>
            </div>
            <p className="m-0 w-full text-[0.75rem] font-semibold text-ink-soft sm:w-auto sm:text-[0.8125rem]">
              Not a diagnosis · for emergencies call your local number
            </p>
          </header>

          <div ref={scrollerRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            <div className="mx-auto flex w-full max-w-[860px] flex-col px-4 py-6 lg:px-7">
              <h2 className="sr-only">Conversation</h2>
              {messages.length === 0 && resumeState === "ready" && !loadingConversation && !conversationError && !sending && (
                <div className="mx-auto flex w-full flex-col items-center gap-6 py-8 text-center">
                  {mode === "orbit" ? (
                    <div className="bubbles-rise flex max-w-md flex-col items-center gap-3">
                      <p className="m-0 font-display text-h2 font-semibold text-ink">Tell me about them</p>
                      <p className="m-0 text-body text-ink-soft">
                        I only know your side, so I won&apos;t judge anyone. This stays between us, and I can help you find words for what you feel.
                      </p>
                      <div className="pearl-chips" role="group" aria-label="Ways to start" style={{ justifyContent: "center" }}>
                        {ORBIT_STARTERS.map((text) => (
                          <button key={text} type="button" className="pearl-chip" disabled={composerDisabled} onClick={() => void sendMessage(text)}>
                            {text}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="bubbles-rise flex max-w-md flex-col items-center gap-3">
                        <BubblesMascot size={96} mood="happy" />
                        <p className="m-0 font-display text-h2 font-semibold text-ink">Hi, I&apos;m Bubbles</p>
                        <p className="m-0 text-body text-ink-soft">
                          Tell me how you&apos;re feeling or ask about your patterns. I can&apos;t diagnose, but I can help you understand and prepare.
                        </p>
                      </div>
                      <PromptCards cards={PROMPT_CARDS} disabled={composerDisabled} onPick={(text) => void sendMessage(text)} />
                    </>
                  )}
                </div>
              )}

              {(resuming || loadingConversation) && (
                <div role="status" aria-label="Opening your chat" className="flex flex-col gap-4">
                  <span className="bubbles-skeleton block h-14 w-3/5 self-end rounded-3xl" />
                  <span className="bubbles-skeleton block h-28 w-4/5 rounded-3xl" />
                  <span className="bubbles-skeleton block h-14 w-1/2 self-end rounded-3xl" />
                </div>
              )}

              {loadProblem && (
                <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-line bg-surface px-5 py-4">
                  <div className="flex items-center gap-3">
                    <p className="m-0 text-body font-bold text-ink">{loadProblem}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={retryLoad}
                      className="bubbles-press min-h-[44px] rounded-full bg-bubbles-pink-ink px-5 text-body-sm font-extrabold text-white bubbles-glow"
                    >
                      Try again
                    </button>
                    <button type="button" onClick={startNewChat} className="min-h-[44px] rounded-full border border-line-strong bg-surface px-5 text-body-sm font-extrabold">
                      Start a new chat
                    </button>
                  </div>
                </div>
              )}

              {hasMore && messages.length > 0 && (
                <div className="flex flex-col items-center gap-1 pb-4">
                  <button
                    type="button"
                    onClick={() => void loadOlder()}
                    disabled={loadingOlder}
                    className="min-h-[44px] rounded-full border border-line-strong bg-surface px-5 text-body-sm font-extrabold text-ink disabled:opacity-60"
                  >
                    {loadingOlder ? "Loading…" : "Show earlier messages"}
                  </button>
                  {olderFailed && (
                    <p role="alert" className="m-0 text-body-sm font-bold text-bubbles-urgent">
                      Couldn&apos;t load earlier messages. Try again.
                    </p>
                  )}
                </div>
              )}

              {continuing && messages.length > 0 && <p className="m-0 pb-4 text-center text-chip font-semibold text-ink-soft">{continuing}</p>}

              <ol aria-label="Messages" className="m-0 flex list-none flex-col gap-[18px] p-0">
                {messages.map((m, i) =>
                  m.role === "user" ? (
                    <li key={m.clientId ?? m.id} className="bubbles-rise flex max-w-[85%] flex-col items-end gap-1 self-end sm:max-w-[min(72%,34rem)]">
                      <p data-private className="m-0 whitespace-pre-wrap break-words rounded-[20px_20px_8px_20px] bg-bubbles-lilac px-[18px] py-3.5 text-body leading-normal text-ink">
                        <span className="sr-only">You: </span>
                        {m.content}
                      </p>
                      {failed?.messageId === m.id && <span className="text-chip font-bold text-bubbles-urgent">Bubbles didn&apos;t reply to this yet</span>}
                    </li>
                  ) : (
                    <BubblesReply
                      key={m.id}
                      message={m}
                      decisions={decisions}
                      eventError={eventErrors[m.id]}
                      onDecide={(ids, confirmed) => void decideEvents(m.id, ids, confirmed)}
                      showAvatar={!isReplyInRun(messages[i - 1])}
                      chips={m.id === chipsFor ? chips : undefined}
                      onChip={(text) => (text === OPEN_ORBIT ? router.push("/orbit/talk") : void sendMessage(text))}
                      chipsDisabled={composerDisabled}
                      feedback={ratings[m.id]}
                      feedbackBusy={ratingBusy[m.id] === true}
                      feedbackFailed={ratingFailed[m.id] === true}
                      onRate={(rating, reason) => void rateReply(m.id, rating, reason)}
                      onConsent={m.id === messages.at(-1)?.id ? () => void allowAi(m.id) : undefined}
                      onDeclineConsent={() => void declineAi(m.id)}
                      onReconsider={reconsiderAi}
                      consentDeclined={declined}
                      consentBusy={consentBusy}
                    />
                  )
                )}
                {sending && (partial ? <PartialReply text={stream.text} /> : <ThinkingBubble calm={loaderCalm(stream) && !harborVoice} />)}
              </ol>
            </div>
          </div>
          <p className="sr-only" aria-live="polite">
            {announcement}
          </p>

          <div className="shrink-0 border-t-2 border-line bg-blush px-4 pb-3 pt-3 lg:px-7 lg:pb-5">
            <div className="mx-auto flex w-full max-w-[860px] flex-col gap-2.5">
              {error && (
                <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-bubbles-urgent/30 bg-tint-urgent px-4 py-2.5">
                  <p className="m-0 text-body-sm font-bold text-bubbles-urgent">{error}</p>
                  {failed && (
                    <button
                      type="button"
                      onClick={() => void sendMessage(failed.text, { messageId: failed.messageId, fresh: failed.fresh })}
                      className="min-h-[44px] rounded-full border border-line-strong bg-surface px-4 text-body-sm font-extrabold text-ink"
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
                    {mode === "orbit" ? "Tell Bubbles" : "Message Bubbles"}
                  </label>
                  <span id="bubbles-message-hint" className={`text-chip font-semibold ${nearLimit ? "text-bubbles-urgent" : "text-ink-soft"}`}>
                    {nearLimit ? (
                      `${input.length.toLocaleString()} / ${MAX_MESSAGE.toLocaleString()} characters`
                    ) : (
                      <span className="hidden sm:inline">Enter to send · Shift+Enter for a new line</span>
                    )}
                  </span>
                </div>
                <div className="flex items-end gap-2.5 rounded-[24px] border border-line-strong bg-surface py-1.5 pl-5 pr-1.5 shadow-[var(--shadow-sm)] transition-[border-color,box-shadow] focus-within:border-bubbles-grape focus-within:shadow-[var(--shadow-glow-accent)]">
                  <textarea
                    id="bubbles-message"
                    ref={inputRef}
                    rows={1}
                    value={input}
                    maxLength={MAX_MESSAGE}
                    disabled={composerDisabled}
                    aria-describedby="bubbles-message-hint"
                    placeholder={mode === "orbit" ? "What is on your heart?" : "Ask Bubbles anything about your health…"}
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
                        ? "bg-bubbles-pink-ink text-white bubbles-glow"
                        : "bg-tint-grape text-bubbles-grape-deep shadow-none"
                    }`}
                  >
                    {sending ? (
                      <span className="inline-flex items-center gap-1" aria-hidden="true">
                        <span className="bubbles-send-dot" />
                        <span className="bubbles-send-dot" />
                        <span className="bubbles-send-dot" />
                      </span>
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
        aria-label="History"
        onClose={() => setDrawerOpen(false)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setDrawerOpen(false);
        }}
        className="m-0 h-dvh max-h-none w-[min(320px,86vw)] max-w-none border-0 bg-surface p-0 backdrop:bg-ink/40"
      >
        {drawerOpen && (
          <div className="bubbles-rise flex h-full flex-col gap-3 overflow-y-auto p-4">
            <div className="flex items-center justify-between">
              <h2 className="m-0 font-display text-h3 font-semibold">History</h2>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                aria-label="Close history"
                className="flex h-11 w-11 items-center justify-center rounded-full border border-line text-ink"
              >
                <Icon d={ICONS.close} size={20} />
              </button>
            </div>
            {conversationList(true)}
          </div>
        )}
      </dialog>
    </main>
  );
}
