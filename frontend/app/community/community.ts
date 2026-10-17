/** Community wording and small decisions, kept pure so they are tested (community.test.ts). Shapes match backend/community_api.py. */

export const TOPIC_LABELS: Record<string, string> = {
  cycle: "Cycle", sleep: "Sleep", mind: "Mind", food: "Food", fitness: "Fitness", skin_hair: "Skin and hair", talk: "Just talking",
};

export type Reactions = { me_too: number; helpful: number };
export type ReactionKind = keyof Reactions;
export type CommunityPost = {
  id: string; alias: string; anonymous: boolean; body: string; created_at: string; mine: boolean; topic?: string; comment_count?: number;
  reactions: Reactions; my_reactions: string[]; status?: "visible" | "held" | "removed"; note?: string;
};
export type Support = { kind: "crisis" | "urgent"; message: string; lines: string } | null;
export type CommunityStatus = {
  enabled: boolean; can_read: boolean; can_post: boolean; reason: "off" | "adults_only" | "consent_needed" | "not_allowed" | null;
  topics: string[]; disclaimer: string; limits: { post: number; comment: number };
};

export const topicLabel = (topic: string | undefined): string => (topic && TOPIC_LABELS[topic]) || "Just talking";

/** The one quiet sentence when the feed is not open to this person. */
export function closedMessage(status: CommunityStatus): string | null {
  if (status.can_read) return null;
  if (status.reason === "adults_only") return "The community is for people 18 and over.";
  return "The community is not open yet. Check back soon.";
}

/** Reading is open without consent; posting needs a yes in Privacy choices. */
export function postingHint(status: CommunityStatus): string | null {
  if (status.can_post) return null;
  if (status.reason === "consent_needed") return "To post, turn on sharing in Privacy choices.";
  if (status.reason === "not_allowed") return "Posting is paused for your account.";
  return null;
}

/** Add a fetched page after the current list without duplicating a post that moved between pages. */
export function appendPage(current: CommunityPost[], page: CommunityPost[]): CommunityPost[] {
  const seen = new Set(current.map((p) => p.id));
  return [...current, ...page.filter((p) => !seen.has(p.id))];
}

/** Flip one of my reactions locally after the server answers { on }. */
export function applyReaction(post: CommunityPost, kind: ReactionKind, on: boolean): CommunityPost {
  const had = post.my_reactions.includes(kind);
  if (had === on) return post;
  return {
    ...post,
    reactions: { ...post.reactions, [kind]: Math.max(0, post.reactions[kind] + (on ? 1 : -1)) },
    my_reactions: on ? [...post.my_reactions, kind].sort() : post.my_reactions.filter((k) => k !== kind),
  };
}

export const statusWord = (status: CommunityPost["status"]): string =>
  status === "held" ? "Waiting for review" : status === "removed" ? "Not shown" : "Shared";
