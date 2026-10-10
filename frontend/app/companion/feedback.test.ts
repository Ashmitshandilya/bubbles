import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { FEEDBACK_REASONS, idsToLoad, isRatableId, parseRatings, ratingsPath } from "./feedback";

const id = (n: number) => `0b7a9c3e-1f2d-4a55-9c1e-${String(n).padStart(12, "0")}`;

describe("reply feedback helpers", () => {
  it("only server-saved reply ids (UUIDs) can be rated", () => {
    expect(isRatableId(id(1))).toBe(true);
    expect(isRatableId("abc")).toBe(false);
    expect(isRatableId("0b7a9c3e-1f2d-4a55-9c1e-local-reply")).toBe(false);
    expect(isRatableId("message-001")).toBe(false);
  });

  it("caps the request at 50 newest ids and drops unratable ones", () => {
    const ids = Array.from({ length: 70 }, (_, i) => id(i));
    const kept = idsToLoad(["short", ...ids]);
    expect(kept).toHaveLength(50);
    expect(kept[49]).toBe(id(69));
    expect(ratingsPath([id(1), id(2)])).toBe(`/chat/feedback?message_ids=${id(1)},${id(2)}`);
  });

  it("reads ratings defensively", () => {
    const parsed = parseRatings({
      ratings: {
        a1234567: { rating: "down", reason: "too_long" },
        b1234567: { rating: "up", reason: "unclear" },
        c1234567: { rating: "sideways" },
        d1234567: { rating: "down", reason: "made up" },
        e1234567: null,
      },
    });
    expect(parsed).toEqual({
      a1234567: { rating: "down", reason: "too_long" },
      b1234567: { rating: "up", reason: "unclear" },
      d1234567: { rating: "down", reason: null },
    });
    expect(parseRatings(null)).toEqual({});
    expect(parseRatings({ ratings: 5 })).toEqual({});
  });

  it("has plain labels with no em-dashes", () => {
    expect(FEEDBACK_REASONS.every((r) => r.label.length > 0 && !r.label.includes("—"))).toBe(true);
  });

  it("never renders the thumbs row on withdrawn or urgent replies (they return earlier in BubblesReply)", () => {
    const src = readFileSync(new URL("./ChatBits.tsx", import.meta.url), "utf8");
    const reply = src.slice(src.indexOf("export function BubblesReply"));
    const thumbs = reply.indexOf("<ReplyFeedback");
    expect(thumbs).toBeGreaterThan(0);
    expect(reply.indexOf("if (message.retracted)")).toBeLessThan(thumbs);
    expect(reply.indexOf("if (isUrgentMessage(message))")).toBeLessThan(thumbs);
    // both early branches return before the calm layout where the thumbs live
    const urgentBlock = reply.slice(reply.indexOf("if (isUrgentMessage(message))"), thumbs);
    expect(urgentBlock).toContain("return (");
  });
});
