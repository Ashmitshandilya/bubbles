/** Reads GET /me/predictions into plain rows: what Bubbles is learning about this person's own days, and how often its guesses held. */
export type LearnedRow = { id: string; title: string; status: "earned" | "learning" | "doubted"; record: string };

const TITLES: Record<string, string> = {
  "sleep_hours->mood": "A short night and your mood",
  "activity_minutes->sleep_hours": "A quiet day and your next night",
  "hydration_ml->mood": "A low-water day and your mood",
  "sleep_hours->activity_minutes": "A short night and how much you move",
};

const NOTE = { earned: "Held up for you", learning: "Still learning", doubted: "Did not hold, so Bubbles is not using it" } as const;

export function readLearned(body: unknown): LearnedRow[] {
  const links = (body as { links?: unknown } | null)?.links;
  if (!Array.isArray(links)) return [];
  const rows: LearnedRow[] = [];
  for (const item of links) {
    const o = item as { link?: unknown; status?: unknown; right?: unknown; of?: unknown };
    if (!Array.isArray(o.link) || o.link.length !== 2) continue;
    const id = `${o.link[0]}->${o.link[1]}`;
    const status = o.status === "earned" || o.status === "doubted" ? o.status : "learning";
    const right = Number(o.right) || 0;
    const of = Number(o.of) || 0;
    rows.push({ id, title: TITLES[id] ?? id.replace("->", " and ").replace(/_/g, " "), status, record: of ? `${NOTE[status]}: right ${right} of ${of} guesses.` : `${NOTE[status]}: no guesses checked yet.` });
  }
  return rows;
}
