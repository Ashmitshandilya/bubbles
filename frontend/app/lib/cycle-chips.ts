// Client-side search, grouping and selection for the symptom/feeling chip picker (the catalogue is fetched once).

import type { Chip, ChipGroup } from "./cycle-types";

export const MAX_CUSTOM_FACTORS = 10;
export const MAX_CUSTOM_LENGTH = 40;

const norm = (s: string) => s.toLowerCase().replaceAll("_", " ").replace(/\s+/g, " ").trim();

function chipScore(chip: Chip, tokens: string[]): number {
  const label = norm(chip.label);
  const id = norm(chip.id);
  const keywords = chip.keywords.map(norm);
  let score = 0;
  for (const token of tokens) {
    if (label.startsWith(token)) score += 4;
    else if (label.includes(token)) score += 3;
    else if (keywords.some((k) => k.startsWith(token))) score += 2;
    else if (keywords.some((k) => k.includes(token)) || id.includes(token)) score += 1;
    else return 0; // every word must match something
  }
  return score;
}

/** All chips matching every word of `query` (label, keywords or id), best matches first. Empty query returns none. */
export function searchChips(groups: ChipGroup[], query: string, limit = 60): Chip[] {
  const tokens = norm(query).split(" ").filter(Boolean);
  if (!tokens.length) return [];
  return groups
    .flatMap((g) => g.chips)
    .map((chip) => ({ chip, score: chipScore(chip, tokens) }))
    .filter((r) => r.score > 0)
    .sort((a, b) => b.score - a.score || a.chip.label.localeCompare(b.chip.label))
    .slice(0, limit)
    .map((r) => r.chip);
}

/** Adds the id when missing, removes it when present. Never mutates. */
export function toggleId(ids: readonly string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id];
}

/** The chips behind the selected ids, in selection order. Unknown ids (an old catalogue) are kept with the id as label. */
export function selectedChips(groups: ChipGroup[], ids: readonly string[]): Array<{ id: string; label: string }> {
  const byId = new Map(groups.flatMap((g) => g.chips).map((c) => [c.id, c.label] as const));
  return ids.map((id) => ({ id, label: byId.get(id) ?? norm(id) }));
}

/** How many selected ids sit in each group, for the group headings. */
export function selectedCounts(groups: ChipGroup[], ids: readonly string[]): Record<string, number> {
  const set = new Set(ids);
  return Object.fromEntries(groups.map((g) => [g.id, g.chips.filter((c) => set.has(c.id)).length]));
}

export type TagResult = { ok: true; list: string[] } | { ok: false; error: string };
export type CustomResult = TagResult;

/** Adds a free-text tag: trimmed, whitespace collapsed, within the length and count limits, no duplicates (case-insensitive). */
export function addTag(list: readonly string[], text: string, max: number, maxLength: number): TagResult {
  const value = text.trim().replace(/\s+/g, " ");
  if (!value) return { ok: false, error: "Type something first." };
  if (value.length > maxLength) return { ok: false, error: `Keep it to ${maxLength} characters or fewer.` };
  if (list.some((x) => x.toLowerCase() === value.toLowerCase())) return { ok: false, error: "You already added that." };
  if (list.length >= max) return { ok: false, error: `You can add up to ${max} of your own.` };
  return { ok: true, list: [...list, value] };
}

export const addCustom = (list: readonly string[], text: string): TagResult => addTag(list, text, MAX_CUSTOM_FACTORS, MAX_CUSTOM_LENGTH);
