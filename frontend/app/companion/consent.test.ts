import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const chatBits = readFileSync(new URL("./ChatBits.tsx", import.meta.url), "utf8");
const reply = chatBits.slice(chatBits.indexOf("export function BubblesReply"));

describe("the outside AI model question", () => {
  it("is never part of an urgent or withdrawn reply (they return before the calm layout)", () => {
    const card = reply.indexOf("<ConsentCard");
    expect(card).toBeGreaterThan(0);
    expect(reply.indexOf("if (message.retracted)")).toBeLessThan(card);
    expect(reply.indexOf("if (isUrgentMessage(message))")).toBeLessThan(card);
  });

  it("replaces the thumbs on the reply that asks the question", () => {
    expect(reply).toContain("!message.consentRequired && isRatableId(message.id)");
  });

  it("says plainly what is sent and that it can be undone, without an em-dash", () => {
    const card = chatBits.slice(chatBits.indexOf("function ConsentCard"), chatBits.indexOf("const THUMB_UP"));
    expect(card).toContain("outside AI model");
    expect(card).toContain("Settings");
    expect(card).not.toContain("—");
  });
});
