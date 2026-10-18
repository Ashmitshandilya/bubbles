import { describe, expect, it } from "vitest";
import { appendPage, applyReaction, blockedLine, closedMessage, postingHint, topicLabel, type CommunityPost, type CommunityStatus } from "./community";

const post = (id: string, over: Partial<CommunityPost> = {}): CommunityPost => ({
  id, alias: "Quiet Otter 4821", anonymous: true, body: "hi", created_at: "2026-10-01T00:00:00Z", mine: false,
  reactions: { me_too: 1, helpful: 0 }, my_reactions: [], ...over,
});
const status = (over: Partial<CommunityStatus>): CommunityStatus => ({
  enabled: true, can_read: true, can_post: true, reason: null, topics: [], disclaimer: "", limits: { post: 1200, comment: 600 }, ...over,
});

describe("community helpers", () => {
  it("names topics and falls back softly", () => {
    expect(topicLabel("skin_hair")).toBe("Skin and hair");
    expect(topicLabel("zzz")).toBe("Just talking");
  });
  it("explains a closed feed and a read-only feed", () => {
    expect(closedMessage(status({}))).toBeNull();
    expect(closedMessage(status({ can_read: false, reason: "adults_only" }))).toMatch(/18/);
    expect(closedMessage(status({ can_read: false, reason: "off" }))).toMatch(/not open/);
    expect(postingHint(status({ can_post: false, reason: "consent_needed" }))).toMatch(/Privacy choices/);
    expect(postingHint(status({}))).toBeNull();
  });
  it("always gives a reason when posting is shut", () => {
    expect(postingHint(status({ can_post: false, reason: "not_allowed" }))).toMatch(/paused/);
    expect(postingHint(status({ can_post: false, reason: null }))).toMatch(/not available/);
    expect(postingHint(status({ can_post: false, reason: "off" }))).toBeTruthy();
  });
  it("says how many people are blocked", () => {
    expect(blockedLine(0)).toMatch(/not blocked/);
    expect(blockedLine(1)).toBe("You have blocked 1 person.");
    expect(blockedLine(3)).toBe("You have blocked 3 people.");
  });
  it("appends a page without duplicates", () => {
    expect(appendPage([post("a"), post("b")], [post("b"), post("c")]).map((p) => p.id)).toEqual(["a", "b", "c"]);
  });
  it("applies a reaction toggle once", () => {
    const on = applyReaction(post("a"), "helpful", true);
    expect(on.reactions.helpful).toBe(1);
    expect(on.my_reactions).toEqual(["helpful"]);
    expect(applyReaction(on, "helpful", true)).toBe(on);
    expect(applyReaction(on, "helpful", false).reactions.helpful).toBe(0);
  });
});
