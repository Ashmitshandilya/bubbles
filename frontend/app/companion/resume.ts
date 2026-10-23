/**
 * Pure rules for opening Talk on the latest chat instead of a blank one: what the URL asks for, how the
 * GET /chat/latest answer is read, how stored rows become chat messages, and how the list should scroll.
 * No React and no DOM, so it runs under plain vitest.
 */
import { adaptHealthEvents, adaptReplySafety } from "../lib/bubbles-events";
import { askHandle } from "../lib/ask-handoff";
import { adaptHarbor } from "../lib/safe-harbor";
import type { ChatMessage } from "./ChatBits";

export interface Entry {
  /** ?new=1: start a blank chat and do not resume anything. */
  fresh: boolean;
  /** ?ask= or ?askref=: a question waiting to be sent once the right chat is open. */
  ask: string | null;
}

export function parseEntry(params: URLSearchParams): Entry {
  return { fresh: params.get("new") === "1", ask: askHandle(params) };
}

/** Rows as GET /chat/latest and GET /chat/conversations/{id}/messages return them (all fields optional on purpose). */
export function mapMessageRows(rows: unknown, conversationId: string): ChatMessage[] {
  if (!Array.isArray(rows)) return [];
  return rows.map((raw, i): ChatMessage => {
    const m = (raw !== null && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
    const base = {
      id: typeof m.id === "string" ? m.id : `${conversationId}-${i}`,
      content: typeof m.content === "string" ? m.content : "",
      createdAt: typeof m.created_at === "string" ? m.created_at : undefined,
    };
    if (m.role === "user") return { ...base, role: "user" };
    // Reloaded history goes through the same adapters as a live reply, so a withdrawn warning stays withdrawn.
    return {
      ...base,
      role: "assistant",
      ...adaptReplySafety(m.safety, m.safety_level, m.kind),
      healthEvents: adaptHealthEvents(m.health_events, undefined),
      consentRequired: m.consent_required === true,
      harbor: adaptHarbor(m.harbor) ?? undefined, // a reload shows the same Safe Harbor reply
    };
  });
}

export type Latest =
  | { kind: "empty" }
  | { kind: "error" }
  | { kind: "chat"; conversationId: string; title: string; messages: ChatMessage[]; hasMore: boolean };

/**
 * Read a GET /chat/latest body. `degraded: true` or an unreadable body is an error (never "no chats yet"), so the
 * person is offered "Try again" and "Start a new chat" instead of a blank screen that hides their history.
 */
export function pickLatest(payload: unknown): Latest {
  if (payload === null || typeof payload !== "object") return { kind: "error" };
  const body = payload as Record<string, unknown>;
  if (body.degraded === true) return { kind: "error" };
  if (body.status !== undefined && body.status !== "success") return { kind: "error" };
  if (!("conversation" in body)) return { kind: "error" };
  const conv = body.conversation;
  if (conv === null) return { kind: "empty" };
  const c = (typeof conv === "object" ? conv : {}) as Record<string, unknown>;
  if (typeof c.id !== "string" || !c.id) return { kind: "error" };
  const messages = mapMessageRows(body.messages, c.id);
  // A conversation row can exist with no messages; treat it as a blank start.
  if (messages.length === 0) return { kind: "empty" };
  return {
    kind: "chat",
    conversationId: c.id,
    title: typeof c.title === "string" ? c.title : "",
    messages,
    hasMore: body.has_more === true,
  };
}

/** The `before` cursor for the next older page: the oldest loaded message's time, or null when it has none. */
export function olderCursor(messages: ChatMessage[]): string | null {
  const first = messages.find((m) => typeof m.createdAt === "string" && m.createdAt);
  return first?.createdAt ?? null;
}

/** Older rows go in front; a row already shown is dropped so a repeated page can never double a message. */
export function prependOlder(current: ChatMessage[], older: ChatMessage[]): ChatMessage[] {
  const have = new Set(current.map((m) => m.id));
  return [...older.filter((m) => !have.has(m.id)), ...current];
}

export type ScrollPlan = "jump" | "smooth" | "anchor" | "none";

/**
 * What the message list should do after it changed.
 * - jump: a conversation was just opened or resumed: land on the last message instantly.
 * - anchor: older messages were added on top: keep the reader where they were.
 * - smooth: a new message arrived or Bubbles started replying: glide down.
 * - none: nothing visible changed (an event card flipped, a rating, a correction).
 */
export function scrollPlan(input: { opened: boolean; prepended: boolean; lastIdChanged: boolean; sendingStarted: boolean }): ScrollPlan {
  if (input.opened) return "jump";
  if (input.prepended) return "anchor";
  if (input.lastIdChanged || input.sendingStarted) return "smooth";
  return "none";
}

/** "Continuing your chat from Tuesday" for a resumed chat whose last message is not from today; otherwise null. */
export function continuingLabel(lastIso: string | undefined, now: Date = new Date()): string | null {
  const last = lastIso ? new Date(lastIso) : null;
  if (!last || Number.isNaN(last.getTime())) return null;
  const dayStart = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((dayStart(now) - dayStart(last)) / 86_400_000);
  if (days <= 0) return null;
  if (days === 1) return "Continuing your chat from yesterday";
  if (days < 7) return `Continuing your chat from ${last.toLocaleDateString("en-GB", { weekday: "long" })}`;
  return `Continuing your chat from ${last.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`;
}
