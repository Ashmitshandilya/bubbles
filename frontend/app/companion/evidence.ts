import type { EvidenceItem } from "../lib/bubbles-events";

/**
 * The source chips shown under a reply: at most `max`, keeping the first of any repeat
 * (same title ignoring case and spaces at the ends, or same link). The backend sends best first.
 */
export function pickSources(items: EvidenceItem[], max = 3): EvidenceItem[] {
  const seen = new Set<string>();
  const out: EvidenceItem[] = [];
  for (const ev of items) {
    if (out.length >= max) break;
    const title = `title:${ev.title.trim().toLowerCase()}`;
    const url = ev.sourceUrl ? `url:${ev.sourceUrl.trim()}` : null;
    if (seen.has(title) || (url && seen.has(url))) continue;
    seen.add(title);
    if (url) seen.add(url);
    out.push(ev);
  }
  return out;
}
