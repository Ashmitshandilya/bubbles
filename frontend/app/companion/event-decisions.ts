// The confirm / dismiss decisions on a reply's health-detail card, as pure logic (event-decisions.test.ts).

export type DecisionState = "saved" | "dismissed" | "retracted";
export type DecisionOutcome = "done" | "withdrawn" | "failed";

/** What the card shows the moment a button is pressed: the person's choice, before the server has answered. */
export function optimistic(ids: string[], confirmed: boolean): Record<string, DecisionState> {
  return Object.fromEntries(ids.map((id) => [id, confirmed ? "saved" : "dismissed"] as const));
}

/** One outcome per id from the batch answer. A missing id counts as failed; 409/410 means Bubbles withdrew it after a correction. */
export function outcomesFromBatch(ids: string[], results: unknown): DecisionOutcome[] {
  const byId = new Map<string, { status?: string; code?: number }>();
  if (Array.isArray(results)) for (const r of results) if (r && typeof r === "object" && typeof (r as { id?: unknown }).id === "string") byId.set((r as { id: string }).id, r as { status?: string; code?: number });
  return ids.map((id) => {
    const r = byId.get(id);
    if (!r) return "failed";
    if (r.status === "confirmed" || r.status === "rejected") return "done";
    return r.code === 409 || r.code === 410 ? "withdrawn" : "failed";
  });
}

/** Commit the outcomes onto the visible state: done keeps the choice, withdrawn settles as retracted, failed rolls back to undecided. */
export function applyOutcomes(
  state: Record<string, string>,
  ids: string[],
  confirmed: boolean,
  outcomes: DecisionOutcome[],
): Record<string, string> {
  const next = { ...state };
  outcomes.forEach((o, i) => {
    if (o === "done") next[ids[i]] = confirmed ? "saved" : "dismissed";
    else if (o === "withdrawn") next[ids[i]] = "retracted";
    else delete next[ids[i]];
  });
  return next;
}
