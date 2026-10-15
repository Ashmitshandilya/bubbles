import { CHAPTERS } from "./story/store";

/** Short mono lines from the Figma pass (Oct 2026); chapters without one just show their number and name. */
const LINES: Record<string, string> = {
  enter: "Cycle-aware. Always human.",
  track: "Less tracking. More talking.",
  cycle: "Your cycle companion.",
  connect: "Context takes its time.",
  remember: "Your words. Your final say.",
  care: "Your story, in your hands.",
  bubbles: "A companion. Not a doctor.",
};

/** "03 / 10 · LESS TRACKING. MORE TALKING." for a chapter key, shown by CSS above that chapter's headline. */
export function eyebrow(key: string): string {
  const i = CHAPTERS.findIndex((c) => c.key === key);
  if (i < 0) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(i + 1)} / ${pad(CHAPTERS.length)} · ${(LINES[key] ?? CHAPTERS[i].label).toUpperCase()}`;
}
