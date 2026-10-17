// Android app (2.0): the feature grid on Today and the bottom dock, following the person's setup (app/lib/experience.ts):
// no body map when the profile hides it, no Cycle when cycle features are off, and no section the profile hides.

import type { Experience } from "./experience";

export type AppTile = { id: string; label: string; href: string; icon: string; blurb: string; tone: string };

export const APP_TILES: readonly AppTile[] = [
  { id: "talk", label: "Talk", href: "/companion", icon: "companion", blurb: "Tell Bubbles anything", tone: "pink" },
  { id: "track", label: "Track", href: "/sleep", icon: "activity", blurb: "Sleep, water, food, more", tone: "sky" },
  { id: "patterns", label: "Patterns", href: "/insights", icon: "insights", blurb: "What connects, gently", tone: "grape" },
  { id: "mind", label: "Mind", href: "/mind", icon: "mood", blurb: "Check in with yourself", tone: "mint" },
  { id: "cycle", label: "Cycle", href: "/cycle", icon: "cycle", blurb: "Your rhythm, day by day", tone: "peach" },
  { id: "fitness", label: "Fitness", href: "/fitness", icon: "fitness", blurb: "Workouts and food plans", tone: "sun" },
  { id: "care", label: "Care", href: "/care", icon: "care", blurb: "Doctor prep and medicines", tone: "sky" },
];

const shown = (id: string, experience: Experience | null) =>
  !experience || (!experience.hiddenSections.includes(id) && (id !== "cycle" || experience.cycleVisible));

export function bodyMapShown(experience: Experience | null): boolean {
  return experience?.bodyMap.visible !== false;
}

export function appTiles(experience: Experience | null): AppTile[] {
  return APP_TILES.filter((tile) => shown(tile.id, experience));
}

export type DockTab = { id: string; label: string; href: string; icon: string };

/** Today, a personal second tab (Body, else Cycle, else Mind), Talk in the centre, Track. More is added by the dock. */
export function dockTabs(experience: Experience | null): [DockTab, DockTab, DockTab, DockTab] {
  const second: DockTab = bodyMapShown(experience)
    ? { id: "patterns", label: "Body", href: "/body", icon: "body" }
    : shown("cycle", experience)
      ? { id: "cycle", label: "Cycle", href: "/cycle", icon: "cycle" }
      : { id: "mind", label: "Mind", href: "/mind", icon: "mood" };
  return [
    { id: "today", label: "Today", href: "/dashboard", icon: "dashboard" },
    second,
    { id: "talk", label: "Talk", href: "/companion", icon: "companion" },
    { id: "track", label: "Track", href: "/sleep", icon: "activity" },
  ];
}
