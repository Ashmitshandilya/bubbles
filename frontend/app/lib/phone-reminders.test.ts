import { describe, expect, it } from "vitest";
import { phoneProblemMessage, phoneRow, pushTestMessage, pushToSave } from "./phone-reminders";

describe("phoneRow", () => {
  it("is offered only in the app, with Firebase in the build and on the server", () => {
    expect(phoneRow(false, true, true)).toBe("hidden");
    expect(phoneRow(true, false, true)).toBe("hidden");
    expect(phoneRow(true, true, false)).toBe("hidden");
    expect(phoneRow(true, null, true)).toBe("checking");
    expect(phoneRow(true, true, true)).toBe("ready");
  });
});

describe("pushToSave", () => {
  it("keeps the phone's choice when settings are saved anywhere else", () => {
    expect(pushToSave("hidden", false, true)).toBe(true);
    expect(pushToSave("checking", false, true)).toBe(true);
    expect(pushToSave("ready", false, true)).toBe(false);
    expect(pushToSave("ready", true, false)).toBe(true);
  });
});

describe("wording", () => {
  const all = [
    ...(["unavailable", "denied", "failed"] as const).map(phoneProblemMessage),
    ...[{ reason: "wait" }, { sent: 1 }, { reason: "no_devices" }, { removed: 1, sent: 0 }, {}].map(pushTestMessage),
  ];

  it("says what happened for each test result", () => {
    expect(pushTestMessage({ sent: 1, removed: 0 })).toMatch(/Test sent/);
    expect(pushTestMessage({ reason: "wait" })).toMatch(/minute/);
    expect(pushTestMessage({ sent: 0, removed: 1 })).toMatch(/isn't connected/);
    expect(pushTestMessage({ reason: "not_ready" })).toMatch(/still show in Bubbles/);
  });

  it("has no em-dashes, digits or health words", () => {
    for (const text of all) {
      expect(text).not.toMatch(/[—–]/);
      expect(text).not.toMatch(/\d/);
      expect(text).not.toMatch(/medicine|dose|symptom|period|pain/i);
    }
  });
});
