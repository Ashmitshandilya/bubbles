/**
 * Pure helpers for the /chat request lifecycle: how long to wait, what a failure means, and what to tell the user.
 * Kept out of the component so the rules are unit-testable (vitest runs in node, with no DOM).
 */

/**
 * POST /chat runs the safety gate, retrieval and one or two AI calls (about 45 seconds each in the worst case),
 * so it must wait far longer than fetchBubbles' 15 second default. It is also never replayed on a timeout:
 * the server may still be working on the first request.
 */
export const CHAT_TIMEOUT_MS = 100_000;

/** fetchBubbles marks the error it throws for a timed-out request with `timedOut: true`. */
export function isTimeoutError(error: unknown): boolean {
  return typeof error === "object" && error !== null && (error as { timedOut?: unknown }).timedOut === true;
}

/** 400 and 404 mean the conversation id is bad or gone: forget it so "Try again" opens a new conversation. */
export function resetsConversation(status: number | null): boolean {
  return status === 400 || status === 404;
}

/** 409 means the message id was already used for different text: a retry must send a fresh id. */
export function needsFreshMessageId(status: number | null): boolean {
  return status === 409;
}

/** User-facing copy for a failed /chat call. `status` is null when no HTTP response arrived at all. */
export function chatErrorMessage(status: number | null, timedOut = false): string {
  if (timedOut || status === 504) {
    return "Bubbles is taking longer than usual to reply. Wait a moment, then try again. Your message may already have gone through.";
  }
  if (status === null) return "Bubbles can't be reached right now. Check your connection and try again.";
  if (status === 400) return "Bubbles couldn't use this conversation. Try again to start a new one.";
  if (status === 401) return "Your session has expired. Sign out and back in, then try again.";
  if (status === 404) return "That conversation is no longer available. Try again to start a new one.";
  if (status === 409) return "This message was already sent with different text. Try again to send it as a new message.";
  if (status === 422) return "Bubbles couldn't read that message. Keep it under 8,000 characters and try again.";
  if (status === 429) return "That's a lot of messages at once. Wait a moment, then try again.";
  if (status === 502 || status === 503) return "Bubbles is temporarily unavailable. Try again shortly.";
  return "Something went wrong on Bubbles' side. Try again in a moment.";
}
