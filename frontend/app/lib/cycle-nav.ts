// The cycle section's tabs: ids (mirrored in the URL hash, e.g. /cycle#calendar) and arrow-key navigation.

export const CYCLE_TABS = [
  { id: "today", label: "Today" },
  { id: "calendar", label: "Calendar" },
  { id: "log", label: "Log" },
  { id: "insights", label: "Insights" },
  { id: "fertility", label: "Fertility" },
  { id: "modes", label: "Modes" },
  { id: "report", label: "Report" },
] as const;

export type CycleTabId = (typeof CYCLE_TABS)[number]["id"];

export function tabFromHash(hash: string): CycleTabId {
  const id = hash.replace(/^#/, "").toLowerCase();
  return CYCLE_TABS.find((t) => t.id === id)?.id ?? "today";
}

/** Tab to move to for a key press on `current`, or null when the key is not a tab-navigation key. */
export function tabForKey(current: CycleTabId, key: string): CycleTabId | null {
  const index = CYCLE_TABS.findIndex((t) => t.id === current);
  const last = CYCLE_TABS.length - 1;
  if (key === "ArrowRight") return CYCLE_TABS[index === last ? 0 : index + 1].id;
  if (key === "ArrowLeft") return CYCLE_TABS[index === 0 ? last : index - 1].id;
  if (key === "Home") return CYCLE_TABS[0].id;
  if (key === "End") return CYCLE_TABS[last].id;
  return null;
}
