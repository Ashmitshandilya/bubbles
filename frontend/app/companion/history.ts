// Pure grouping for the Talk history list. No React: unit-tested in history-group.test.ts.
import type { ConversationSummary } from "./ChatBits";

/** Talk first, then Heart-to-heart. With no Heart-to-heart threads there is one plain list and no headings. */
export function groupByMode(items: ConversationSummary[]): Array<{ label: string | null; items: ConversationSummary[] }> {
  const orbit = items.filter((c) => c.mode === "orbit");
  if (!orbit.length) return [{ label: null, items }];
  const talk = items.filter((c) => c.mode !== "orbit");
  return [...(talk.length ? [{ label: "Talk", items: talk }] : []), { label: "Heart-to-heart", items: orbit }];
}
