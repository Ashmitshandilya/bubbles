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

  it("names the outside AI model and where to undo it, without repeating the reply or an em-dash", () => {
    const card = chatBits.slice(chatBits.indexOf("function ConsentCard"), chatBits.indexOf("const THUMB_UP"));
    expect(card).toContain("outside AI model");
    expect(card).toContain("You can change this any time in Settings.");
    // What is sent is said once, in the reply text from the server, not again in the card.
    expect(card).not.toContain("short summary of your own notes");
    expect(card).toContain("w-full");
    expect(card).not.toContain("—");
  });
});
