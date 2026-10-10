import { describe, expect, it } from "vitest";
import { FEEDBACK_REASONS, idsToLoad, isRatableId, parseRatings, ratingsPath } from "./feedback";

describe("reply feedback helpers", () => {
  it("only server-saved reply ids can be rated", () => {
    expect(isRatableId("0b7a9c3e-1f2d-4a55-9c1e-2d3f4a5b6c7d")).toBe(true);
    expect(isRatableId("abc")).toBe(false);
    expect(isRatableId("0b7a9c3e-1f2d-4a55-9c1e-local-reply")).toBe(false);
    expect(isRatableId("has spaces in it ok")).toBe(false);
  });

  it("caps the request at 50 newest ids and drops unratable ones", () => {
    const ids = Array.from({ length: 70 }, (_, i) => `message-${String(i).padStart(3, "0")}`);
    const kept = idsToLoad(["short", ...ids]);
    expect(kept).toHaveLength(50);
    expect(kept[49]).toBe("message-069");
    expect(ratingsPath(["message-001", "message-002"])).toBe("/chat/feedback?message_ids=message-001,message-002");
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
});
