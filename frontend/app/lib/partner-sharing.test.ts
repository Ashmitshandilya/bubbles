import { describe, expect, it } from "vitest";
import { canSave, codeIsComplete, daysLeft, formatCodeInput, hoursLeft, inviteMessage, shareEndpoint, shareLink, whatsappLink } from "./partner-sharing";

describe("partner sharing helpers", () => {
  it("builds the public endpoint and the partner-facing link from a token", () => {
    expect(shareEndpoint("abc_DEF-123", "https://api.example.com")).toBe("https://api.example.com/partner/abc_DEF-123");
    expect(shareLink("https://heybubbles.in/", "tok")).toBe("https://heybubbles.in/partner/tok");
    expect(shareEndpoint("a/b", "https://x")).toBe("https://x/partner/a%2Fb");
  });

  it("counts whole days and hours left and never goes negative", () => {
    const now = Date.parse("2026-10-10T00:00:00Z");
    expect(daysLeft("2026-10-17T00:00:00Z", now)).toBe(7);
    expect(daysLeft("2026-10-10T06:00:00Z", now)).toBe(1);
    expect(daysLeft("2026-10-01T00:00:00Z", now)).toBe(0);
    expect(daysLeft(null, now)).toBeNull();
    expect(daysLeft("not a date", now)).toBeNull();
    expect(hoursLeft("2026-10-11T23:30:00Z", now)).toBe(48);
    expect(hoursLeft("2026-10-09T00:00:00Z", now)).toBe(0);
  });

  it("only allows saving with something chosen, and a note when the note is chosen", () => {
    expect(canSave([], "")).toBe(false);
    expect(canSave(["sleep"], "")).toBe(true);
    expect(canSave(["support_note"], "  ")).toBe(false);
    expect(canSave(["support_note"], "tea helps")).toBe(true);
    expect(canSave(["sleep"], "x".repeat(501))).toBe(false);
  });

  it("tidies a typed invite code", () => {
    expect(formatCodeInput("abcd efgh")).toBe("ABCD-EFGH");
    expect(formatCodeInput("ab-cd")).toBe("ABCD");
    expect(formatCodeInput("abcdefghij")).toBe("ABCD-EFGH");
    expect(codeIsComplete("ABCD-EFGH")).toBe(true);
    expect(codeIsComplete("ABCD")).toBe(false);
  });

  it("makes share messages that carry only an address or a code", () => {
    expect(decodeURIComponent(whatsappLink("see https://heybubbles.in/partner/tok"))).toContain("https://heybubbles.in/partner/tok");
    const msg = inviteMessage("ABCD-EFGH", "https://heybubbles.in/");
    expect(msg).toContain("ABCD-EFGH");
    expect(msg).toContain("https://heybubbles.in/partner");
    expect(msg).not.toMatch(/period|sleep|cycle/i);
  });
});
