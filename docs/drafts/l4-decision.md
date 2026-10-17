## Insight details: one sheet, one id, one confidence word (A6)

- Every insight has a stable URL-safe id: `rec:<event_type>:<subject>` (repeated), `co:<a>|<b>` (together), `<x>-><y>` (links between logged series). The ids are on `/patterns/analyze`, `/insights/weekly`, the brief's correlations and `/wellness/associations`, and `GET /insights/{id}` (owner-scoped, `days` 7..365) returns the detail with dated entries (ISO days only, never free text).
- One detail sheet (`frontend/app/insights/InsightDetailSheet.tsx`, native `<dialog>`) with six sections in a fixed order: What Bubbles saw, The days and numbers (a real table or a gap sentence), How sure, What this does not mean, One thing to try, Ask Bubbles about it. Built by the pure `detail.ts` for Patterns, links and Today.
- One confidence scale: the server's word (low, medium, high) in `confidence_label`; older responses fall back to the same 0.75 / 0.5 cut-offs (`insights/confidence.ts`). Links between logged series never read High unless the direction repeated.
- Reach: an explicit "Details" button (44 px, name includes the headline) on every Patterns card, link card and Today pattern/also card. Deep link `/insights?item=<id>` is read once, cleared with `history.replaceState`, and says "This pattern is no longer in the last N days" if the window no longer holds it.
- "Your week" on Today never opens to an empty box: a failed call says so with Try again; a week with too little logged says it is a gap.
- Organ-map evidence: the server sends only the newest entries, so the panel says "Showing the N newest of M entries" instead of implying the list is complete.
- Wording: Insights "Sources" is now "Read more", the raw snippet is gone.
- Default chosen: Today's cards still keep the small "Why does Bubbles think this?" fold for the short reasons; Details is the full view.
