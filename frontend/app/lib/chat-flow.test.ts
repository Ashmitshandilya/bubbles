/**
 * Checks for the /chat request lifecycle rules. Run: npx vitest run app/lib/chat-flow.test.ts
 */
import { describe, expect, it } from "vitest";
import { CHAT_TIMEOUT_MS, chatErrorMessage, isTimeoutError, needsFreshMessageId, resetsConversation } from "./chat-flow";

describe("chatErrorMessage", () => {
  it("keeps the existing copy for the existing statuses", () => {
    expect(chatErrorMessage(null)).toContain("Check your connection");
    expect(chatErrorMessage(401)).toContain("session has expired");
    expect(chatErrorMessage(422)).toContain("8,000");
    expect(chatErrorMessage(429)).toContain("a lot of messages");
    expect(chatErrorMessage(502)).toContain("temporarily unavailable");
    expect(chatErrorMessage(503)).toContain("temporarily unavailable");
    expect(chatErrorMessage(500)).toContain("Something went wrong");
  });

  it("explains a 409 as a reused message id and a 400/404 as a dead conversation", () => {
    expect(chatErrorMessage(409)).toContain("already sent with different text");
    expect(chatErrorMessage(400)).toContain("start a new one");
    expect(chatErrorMessage(404)).toContain("start a new one");
  });

  it("describes a timeout as slow, never as a lost connection", () => {
    for (const text of [chatErrorMessage(null, true), chatErrorMessage(504)]) {
      expect(text).toContain("longer than usual");
      expect(text.toLowerCase()).not.toContain("connection");
      expect(text.toLowerCase()).not.toContain("can't be reached");
    }
  });
});

describe("conversation recovery", () => {
  it("resets the conversation on 400 and 404 only", () => {
    expect(resetsConversation(400)).toBe(true);
    expect(resetsConversation(404)).toBe(true);
    for (const status of [null, 401, 409, 422, 429, 500, 502, 503, 504]) expect(resetsConversation(status)).toBe(false);
  });

  it("asks for a fresh message id on 409 only", () => {
    expect(needsFreshMessageId(409)).toBe(true);
    for (const status of [null, 400, 404, 500, 504]) expect(needsFreshMessageId(status)).toBe(false);
  });
});

describe("isTimeoutError", () => {
  it("recognises the error fetchBubbles throws for a timeout", () => {
    expect(isTimeoutError(Object.assign(new Error("slow"), { timedOut: true }))).toBe(true);
    expect(isTimeoutError(Object.assign(new Error("net"), { timedOut: false }))).toBe(false);
    for (const other of [new Error("x"), null, undefined, "timedOut", { timedOut: "true" }]) expect(isTimeoutError(other)).toBe(false);
  });
});

describe("CHAT_TIMEOUT_MS", () => {
  it("outlasts the backend worst case (a 45 second AI call, retried once)", () => {
    expect(CHAT_TIMEOUT_MS).toBeGreaterThan(90_000);
  });
});
