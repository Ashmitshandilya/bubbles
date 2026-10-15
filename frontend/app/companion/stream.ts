/**
 * Talk to POST /chat/stream (server-sent events) and fall back to the plain POST /chat on any trouble.
 *
 * The chat must work completely when /chat/stream does not exist (404), is buffered by a proxy, or breaks halfway:
 * the same message id goes to /chat, which replays a stored reply instead of answering twice. No React here.
 *
 * Events: meta (conversation_id, user_message_id, safety, kind, consent_required), delta (text already passed
 * through the dose scrubber), done (the same JSON /chat returns), error.
 */
import { CHAT_TIMEOUT_MS } from "../lib/chat-flow";

export type Fetcher = (path: string, init?: RequestInit, limits?: { timeoutMs?: number; retries?: number }) => Promise<Response>;

export interface SseEvent {
  event: string;
  data: string;
}

/** Incremental parser for text/event-stream: feed chunks, get whole events. Comments (": ping") are ignored. */
export function createSseParser(): { push: (chunk: string) => SseEvent[] } {
  let buffer = "";
  return {
    push(chunk: string) {
      buffer += chunk.replace(/\r\n?/g, "\n");
      const out: SseEvent[] = [];
      let cut: number;
      while ((cut = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        let event = "message";
        const data: string[] = [];
        for (const line of block.split("\n")) {
          if (!line || line.startsWith(":")) continue;
          const colon = line.indexOf(":");
          const field = colon === -1 ? line : line.slice(0, colon);
          const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
          if (field === "event") event = value;
          else if (field === "data") data.push(value);
        }
        if (data.length) out.push({ event, data: data.join("\n") });
      }
      return out;
    },
  };
}

export interface StreamMeta {
  conversationId: string | null;
  userMessageId: string | null;
  /** GREEN, AMBER or RED as the safety gate decided; null when the server did not say. */
  level: string | null;
  kind: string | null;
  consentRequired: boolean;
}

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}
const str = (v: unknown) => (typeof v === "string" && v ? v : null);

export function parseMeta(data: unknown): StreamMeta {
  const d = record(data);
  const safety = record(d.safety);
  return {
    conversationId: str(d.conversation_id),
    userMessageId: str(d.user_message_id),
    level: str(safety.level) ?? str(d.safety_level) ?? str(d.level),
    kind: str(d.kind),
    consentRequired: d.consent_required === true,
  };
}

/** The text of a delta event, whatever shape it came in ({"text": ...}, {"delta": ...} or a bare JSON string). */
export function parseDelta(data: unknown): string {
  if (typeof data === "string") return data;
  const d = record(data);
  return str(d.text) ?? str(d.delta) ?? str(d.content) ?? "";
}

export interface StreamView {
  meta: StreamMeta | null;
  text: string;
}
export const emptyStream: StreamView = { meta: null, text: "" };

/**
 * Show the words as they arrive only for an ordinary calm reply: the gate said GREEN, no consent question and
 * not a special kind. Urgent, caution and deterministic replies wait for `done` and render through their own cards.
 */
export function showPartial(view: StreamView): boolean {
  const m = view.meta;
  if (!m || view.text.trim() === "") return false;
  return m.level === "GREEN" && !m.consentRequired && (m.kind === null || m.kind === "reply");
}

/** Whether the waiting loader may show the mascot: not once the gate has said caution or urgent. */
export function loaderCalm(view: StreamView): boolean {
  const level = view.meta?.level;
  return !level || level === "GREEN";
}

export class ChatHttpError extends Error {
  readonly status: number | null;
  readonly timedOut: boolean;
  constructor(status: number | null, timedOut = false) {
    super(timedOut ? "chat timed out" : `chat ${status ?? "unreachable"}`);
    this.status = status;
    this.timedOut = timedOut;
  }
}

function isTimeout(error: unknown): boolean {
  return typeof error === "object" && error !== null && (error as { timedOut?: unknown }).timedOut === true;
}

/** Statuses that mean "this server has no stream": remembered for the page's lifetime. */
const NO_STREAM = new Set([404, 405, 501]);
let streamUnavailable = false;
/** Test hook: forget what an earlier call learned. */
export function resetStreamProbe(): void {
  streamUnavailable = false;
}

/** A refusal that /chat would repeat is shown as it is; anything else is worth one try on the plain route. */
function fallsBack(status: number): boolean {
  return NO_STREAM.has(status) || status >= 500;
}

const IDLE_MS = 30_000;

export interface ChatCall {
  fetcher: Fetcher;
  body: string;
  onMeta?: (meta: StreamMeta) => void;
  onDelta?: (text: string) => void;
  /** Quiet time (no event, not even a ping) after which the stream is given up on. */
  idleMs?: number;
  /** Ceiling for the whole stream. */
  totalMs?: number;
}

async function viaStream(call: ChatCall): Promise<unknown | null> {
  let response: Response;
  try {
    response = await call.fetcher(
      "/chat/stream",
      { method: "POST", body: call.body, headers: { Accept: "text/event-stream" } },
      { timeoutMs: CHAT_TIMEOUT_MS, retries: 0 }
    );
  } catch (error) {
    if (isTimeout(error)) throw new ChatHttpError(null, true);
    return null;
  }
  if (!response.ok) {
    if (NO_STREAM.has(response.status)) streamUnavailable = true;
    if (fallsBack(response.status)) return null;
    throw new ChatHttpError(response.status);
  }
  // A proxy or an older server may answer with the plain JSON: that is the reply.
  if ((response.headers.get("content-type") ?? "").includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  if (!response.body) return null;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser();
  let payload: unknown = null;
  let idle = false;
  let over = false;
  const stop = (why: "idle" | "over") => {
    if (why === "idle") idle = true;
    else over = true;
    void reader.cancel().catch(() => undefined);
  };
  let idleTimer = setTimeout(() => stop("idle"), call.idleMs ?? IDLE_MS);
  const totalTimer = setTimeout(() => stop("over"), call.totalMs ?? CHAT_TIMEOUT_MS);
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => stop("idle"), call.idleMs ?? IDLE_MS);
      for (const ev of parser.push(decoder.decode(value, { stream: true }))) {
        let data: unknown = ev.data;
        try {
          data = JSON.parse(ev.data);
        } catch {
          // a bare text delta is fine
        }
        if (ev.event === "meta") call.onMeta?.(parseMeta(data));
        else if (ev.event === "delta") call.onDelta?.(parseDelta(data));
        else if (ev.event === "done") payload = data;
        else if (ev.event === "error") return null;
      }
      if (payload !== null) break;
    }
  } catch {
    return null;
  } finally {
    clearTimeout(idleTimer);
    clearTimeout(totalTimer);
    void reader.cancel().catch(() => undefined);
  }
  if (over) throw new ChatHttpError(null, true);
  if (idle) return null;
  return payload;
}

async function viaChat(call: ChatCall): Promise<unknown> {
  let response: Response;
  try {
    // Chat waits far longer than other calls and is never replayed on a timeout (see CHAT_TIMEOUT_MS).
    response = await call.fetcher("/chat", { method: "POST", body: call.body }, { timeoutMs: CHAT_TIMEOUT_MS, retries: 0 });
  } catch (error) {
    throw new ChatHttpError(null, isTimeout(error));
  }
  if (!response.ok) throw new ChatHttpError(response.status);
  return response.json();
}

/**
 * Ask Bubbles. Tries the stream first (unless this page already learned there is none), and on any trouble
 * sends the same body to POST /chat. Throws ChatHttpError for a refusal or a timeout; resolves with the
 * final reply JSON either way.
 */
export async function requestChat(call: ChatCall): Promise<{ payload: unknown; via: "stream" | "chat" }> {
  if (!streamUnavailable) {
    const payload = await viaStream(call);
    if (payload !== null && typeof payload === "object") return { payload, via: "stream" };
  }
  return { payload: await viaChat(call), via: "chat" };
}
