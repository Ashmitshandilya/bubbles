import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { PRIVACY_NOTICE_VERSION } from "./privacy-notice-version";
import { aiCardView, changeBody, historyLine, readHistory, readOverview, readPurpose, withPurpose } from "./consents";

const purpose = (over: Record<string, unknown> = {}) => ({
  id: "partner_sharing", title: "Share summaries with one person", description: "d", text_version: "2026-10a", text_hash: "abc123", available: true,
  granted: false, decision: "none", decided_at: null, ...over,
});

describe("reading the server's answer", () => {
  it("keeps the order and the fields of every purpose", () => {
    const out = readOverview({ policy_version: "2026-10-16", purposes: [purpose(), purpose({ id: "push_notifications", granted: true, decision: "granted" })], disclosures: [{ id: "service_storage", title: "t", text: "x" }] });
    expect(out?.purposes.map((p) => [p.id, p.granted])).toEqual([["partner_sharing", false], ["push_notifications", true]]);
    expect(out?.disclosures[0].id).toBe("service_storage");
  });

  it("drops rows it cannot trust and gives up on nonsense", () => {
    expect(readOverview({ purposes: [{ id: "x" }] })).toBeNull();
    expect(readOverview(null)).toBeNull();
    expect(readPurpose({ ...purpose(), granted: "yes" })).toBeNull();
    expect(readOverview({ purposes: [purpose(), { nope: 1 }] })?.purposes).toHaveLength(1);
  });

  it("reads the history and skips broken rows", () => {
    const out = readHistory({ events: [{ purpose: "ai_chat_processing", title: "T", granted: true, source: "chat_card", created_at: "2026-10-14T10:00:00+00:00" }, { purpose: "" }, 5] });
    expect(out).toHaveLength(1);
    expect(readHistory({})).toEqual([]);
  });
});

describe("history lines", () => {
  const base = { purpose: "p", title: "t", granted: true, source: "chat_card", createdAt: "2026-10-14T10:00:00+00:00", kind: "consent" as const };
  it("says what happened, where and when, in plain words", () => {
    expect(historyLine(base, "en-GB")).toBe("Turned on in chat, 14 Oct 2026");
    expect(historyLine({ ...base, granted: false, source: "settings" }, "en-GB")).toBe("Turned off in Privacy choices, 14 Oct 2026");
    expect(historyLine({ ...base, kind: "acknowledgement", source: "signup" }, "en-GB")).toBe("Read when you signed up, 14 Oct 2026");
  });
  it("survives an unknown source and a bad date", () => {
    expect(historyLine({ ...base, source: "mystery", createdAt: "nonsense" })).toBe("Turned on");
  });
});

describe("changes", () => {
  const p = readPurpose(purpose())!;
  it("a yes quotes the wording, a no does not need to", () => {
    expect(JSON.parse(changeBody(p, true))).toEqual({ granted: true, source: "settings", text_hash: "abc123" });
    expect(JSON.parse(changeBody(p, false, "chat_card"))).toEqual({ granted: false, source: "chat_card" });
  });
  it("swaps in the state the server returned", () => {
    const list = [p, readPurpose(purpose({ id: "other" }))!];
    const next = readPurpose(purpose({ granted: true, decision: "granted" }));
    expect(withPurpose(list, next).map((x) => x.granted)).toEqual([true, false]);
    expect(withPurpose(list, null)).toBe(list);
  });
});

describe("the chat card", () => {
  it("asks until there is an answer, then stays quiet", () => {
    expect(aiCardView(undefined)).toBe("ask");
    expect(aiCardView(readPurpose(purpose()))).toBe("ask");
    expect(aiCardView(readPurpose(purpose({ decision: "declined" })))).toBe("declined");
    expect(aiCardView(readPurpose(purpose({ granted: true, decision: "granted" })))).toBe("granted");
  });
});

describe("the privacy notice version", () => {
  it("is the same number the server stamps on every decision", () => {
    const server = readFileSync(new URL("../../../backend/consent.py", import.meta.url), "utf8");
    expect(server).toContain(`POLICY_VERSION = "${PRIVACY_NOTICE_VERSION}"`);
  });
  it("is shown on the privacy page", () => {
    expect(readFileSync(new URL("../privacy/page.tsx", import.meta.url), "utf8")).toContain("PRIVACY_NOTICE_VERSION");
  });
});

describe("the screens", () => {
  const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

  it("the chat card has an equal No next to the Yes and does not repeat once answered", () => {
    const bits = read("../companion/ChatBits.tsx");
    const client = read("../companion/CompanionClient.tsx");
    expect(bits).toContain("No, not now");
    expect(client).toContain("source: \"chat_card\"");
    expect(client).toContain("consent_ask");
  });

  it("Privacy choices has a real switch per row, a history, and no em-dash", () => {
    const screen = read("../privacy-choices/PrivacyChoicesClient.tsx");
    expect(screen).toContain('role="switch"');
    expect(screen).toContain("What you agreed to");
    expect(screen).not.toContain("—");
    expect(screen).not.toContain("confirm(");
  });

  it("Settings links to it, and the sign-up form asks for the acknowledgement", () => {
    expect(read("../settings/SettingsClient.tsx")).toContain('href="/privacy-choices"');
    const login = read("../login/page.tsx");
    expect(login).toContain("I have read the");
    expect(login).toContain("rememberAcknowledgement");
  });
});
