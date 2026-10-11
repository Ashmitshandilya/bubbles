import { describe, expect, it } from "vitest";
import { NOTICE_KEY, NOTICE_TEXT, dismissNotice, noticeBelongsOn, shouldShowNotice, type NoticeStore } from "./privacy-notice";

const memory = (): NoticeStore & { data: Map<string, string> } => {
  const data = new Map<string, string>();
  return { data, getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
};

describe("privacy notice", () => {
  it("shows until it is dismissed, then stays away", () => {
    const store = memory();
    expect(shouldShowNotice(store)).toBe(true);
    dismissNotice(store);
    expect(store.data.get(NOTICE_KEY)).toBe("1");
    expect(shouldShowNotice(store)).toBe(false);
  });

  it("copes with blocked or throwing storage", () => {
    const throwing: NoticeStore = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(shouldShowNotice(throwing)).toBe(true);
    expect(() => dismissNotice(throwing)).not.toThrow();
    expect(shouldShowNotice(null)).toBe(true);
    expect(() => dismissNotice(null)).not.toThrow();
  });

  it("only promises what the app really does", () => {
    expect(NOTICE_TEXT).toMatch(/no ads/i);
    expect(NOTICE_TEXT).not.toContain("—");
  });

  it("shows on the pages a new visitor sees and stays out of the signed-in app", () => {
    for (const p of ["/", "/login", "/privacy", "/terms", "/partner/abc", "/cycle/partner/abc"]) expect(noticeBelongsOn(p)).toBe(true);
    for (const p of ["/dashboard", "/companion", "/care", "/settings", "/health", "/cycle", "/fitness/diet", "/callback"]) expect(noticeBelongsOn(p)).toBe(false);
  });
});
