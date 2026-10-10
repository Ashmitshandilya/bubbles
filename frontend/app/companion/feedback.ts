/** Thumbs on Bubbles replies. Pure helpers for the chat screen; the server keeps only a rating and one fixed reason. */

export type Rating = "up" | "down";
export type FeedbackReason = "unclear" | "not_helpful" | "too_long" | "worried_me" | "other";
export interface Feedback {
  rating: Rating;
  reason?: FeedbackReason | null;
}

export const FEEDBACK_REASONS: { id: FeedbackReason; label: string }[] = [
  { id: "unclear", label: "It was unclear" },
  { id: "not_helpful", label: "It didn't help" },
  { id: "too_long", label: "Too long" },
  { id: "worried_me", label: "It worried me" },
  { id: "other", label: "Something else" },
];

const MESSAGE_ID = /^[A-Za-z0-9_-]{8,64}$/;
const MAX_IDS = 50;

/** Only a reply the server saved can be rated: a local placeholder id (ends in "-reply") has nothing to attach to. */
export function isRatableId(id: string): boolean {
  return MESSAGE_ID.test(id) && !id.endsWith("-reply");
}

/** The newest ids last, capped at what one request may carry. */
export function idsToLoad(ids: string[]): string[] {
  return ids.filter(isRatableId).slice(-MAX_IDS);
}

export function ratingsPath(ids: string[]): string {
  return `/chat/feedback?message_ids=${idsToLoad(ids).map(encodeURIComponent).join(",")}`;
}

/** Reads GET /chat/feedback defensively: anything that is not a known rating is ignored. */
export function parseRatings(payload: unknown): Record<string, Feedback> {
  const out: Record<string, Feedback> = {};
  const raw = (payload as { ratings?: unknown } | null)?.ratings;
  if (!raw || typeof raw !== "object") return out;
  for (const [id, value] of Object.entries(raw as Record<string, unknown>)) {
    const v = value as { rating?: unknown; reason?: unknown } | null;
    if (!v || (v.rating !== "up" && v.rating !== "down")) continue;
    const reason = FEEDBACK_REASONS.some((r) => r.id === v.reason) ? (v.reason as FeedbackReason) : null;
    out[id] = { rating: v.rating, reason };
  }
  return out;
}
