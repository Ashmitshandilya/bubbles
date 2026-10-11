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

  it("says in visible text what is sent and where to undo it, without an em-dash", () => {
    const card = chatBits.slice(chatBits.indexOf("function ConsentCard"), chatBits.indexOf("const THUMB_UP"));
    // Visible paragraph text, not only the screen-reader label: the card can sit under an urgent reply that does not say it.
    const visible = card.replace(/aria-label="[^"]*"/g, "").replace(/\s+/g, " ");
    for (const part of ["go to an outside AI model", "this message", "recent messages", "profile and notes", "date of birth", "gender", "You can change this any time in Settings."]) {
      expect(visible).toContain(part);
    }
    expect(card).toContain("w-full");
    expect(card).not.toContain("—");
  });
});
