// The admin tab registry: one line per tab. To add a tab add { id, label } to TABS in format.ts and one
// entry here pointing at a panel in its own file (e.g. ./panels-moderation). `ranges` says which time picker the tab gets.
import type { ReactNode } from "react";
import type { RangeId, TabId, ViewRange } from "./format";
import { AiPanel, ApiPanel, LogsPanel, OverviewPanel, SettingsPanel } from "./panels";
import { LivePanel } from "./panels-live";
import { ModerationPanel } from "./panels-moderation";
import { OverallPanel } from "./panels-overall";

export type TabSpec = { ranges: "standard" | "overall" | "none"; render: (range: ViewRange) => ReactNode };

export const PANELS: Record<TabId, TabSpec> = {
  overview: { ranges: "standard", render: (r) => <OverviewPanel range={r as RangeId} /> },
  overall: { ranges: "overall", render: (r) => <OverallPanel range={r} /> },
  ai: { ranges: "standard", render: (r) => <AiPanel range={r as RangeId} /> },
  live: { ranges: "none", render: () => <LivePanel /> },
  api: { ranges: "standard", render: (r) => <ApiPanel range={r as RangeId} /> },
  logs: { ranges: "standard", render: (r) => <LogsPanel range={r as RangeId} /> },
  moderation: { ranges: "none", render: () => <ModerationPanel /> },
  settings: { ranges: "none", render: () => <SettingsPanel /> },
};
