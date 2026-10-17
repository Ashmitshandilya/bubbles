# A6. Insight details: problem statement and what was built

Line numbers are from the session branch before this lane's change (commit 7b3b038).

## Problem

A person sees "Your sleep has moved" or "Headache came up 5 times" and cannot find out why. Every insight lives on one of five
surfaces (Today folds, Patterns page, link cards, weekly recap, organ-map evidence) and none has a detail view or an address.
Affected: everyone who logs, most of all people using a screen reader or keyboard only (links share one name, headlines are not
headings) and people on a phone, where the only path was a bare `/insights` list.

## Root causes

1. Today's "See the evidence" and "Why does Bubbles think this?" go to bare `/insights`: `TodaySections.tsx:316` (`whyHref`), `today.ts:339`
   (`whyHref: "/insights"`). `InsightsClient.tsx` read no id, hash or query, so the link landed on the top of an unrelated page.
2. No shared id. Today used positional ids (`insight-N`, `corr-N`, `today.ts:395`), Patterns used `r-<type>-<subject>` / `c-<a>-<b>`
   (`patterns.ts:73,88`), links used `x->y`. The same finding had three names.
3. Evidence was a count sentence. `source_event_ids` (`pattern_engine.py:151,204`, `weekly_insights.py:60,70`) could not be resolved: no
   `GET /insights/{id}`, no dated entries, no pairs. Fields the API returns (deviations, rho/q/lag, supporting_events,
   suggested_action) were never rendered.
4. Three confidence scales behind one chip: entry confidence in the pattern engine, a count heuristic `0.3 + 0.05 * evidence`
   (`weekly_insights.py:108-110`), and strength words for links.
5. Accessibility: card headlines were `<p>`/`<strong>`, link names were not unique, "Your week" opened to an empty box when its call failed.

## What changed

Backend (additive, no schema change)
- One stable URL-safe id per insight: `rec:<type>:<subject>`, `co:<a>|<b>`, `x->y`, `gap:week` (`pattern_engine.slug/recurrence_id/correlation_id`),
  on `/patterns/analyze`, `/insights/weekly` (`schemas.InsightItem.id`), the brief's correlations and `/wellness/associations`.
- One confidence word (`confidence_label`: low/medium/high) from `pattern_engine.recurrence_confidence/correlation_confidence`; the
  weekly number now agrees with it.
- Dated detail: `occurrences` (newest 14, ISO day + event id), correlation `pairs` (newest 12), association `pairs`, `p`, `repeated`,
  `limitations` list. Days only, never free text.
- `GET /insights/{id}?days=7..365` (`insights_api.py`): owner-scoped by `user_id`, id length capped at 120, unknown or malformed id is a
  plain 404, `source_event_ids` stripped, retracted/rejected rows never count. Registered after `/insights/weekly` so that path wins.

Frontend
- `app/insights/detail.ts` (`toDetail`, pure): six sections in one order for every kind. `confidence.ts`: one scale.
- `InsightDetailSheet.tsx`: native modal `<dialog>`, heading focus on open, `aria-labelledby`, Esc/backdrop/44 px Close, focus returns to
  the trigger, scroll lock. Android back already closes `dialog[open]` (`NativeBridge.tsx:28`), so no Android change was needed.
- Details button (44 px, name "Details about <headline>") on every Patterns card, link card and Today pattern card; headlines are
  `<h3>`. `/insights?item=<id>` is read once, cleared with `history.replaceState`, falls back to "This pattern is no longer in the last N days".
- "Your week" never opens empty; organ-map evidence says "Showing the N newest of M entries".
- Replaced the session branch's smaller frontend-only first pass (`components/InsightDetailSheet.tsx`, old `detail.ts`) with this one.

Voice and consent: no authority names anywhere (tested), no cause or diagnosis wording. Insights only read the person's own saved events;
what is saved is already governed by `consent.is_granted` at write time, and no new write path exists here.
Today's first-run tour selectors (`#today-ask`, quick-log, signals, body-map, profile-link) were not touched.
