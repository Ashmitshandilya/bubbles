"use client";

// Accessible tablist (arrow keys, Home/End, roving tabindex) mirrored in the URL hash, plus the always-there
// "Log today" button. Only the active panel's content is mounted, so each tab loads its own data on demand.

import { useCallback, useEffect, useRef, useState } from "react";
import { CYCLE_TABS, tabForKey, tabFromHash, type CycleTabId } from "../../app/lib/cycle-nav";
import { useCycle } from "./CycleStore";
import { CalendarTab } from "./CalendarTab";
import { FertilityTab } from "./FertilityTab";
import { InsightsTab } from "./InsightsTab";
import { LogTab } from "./LogTab";
import { ModesTab } from "./ModesTab";
import { ReportTab } from "./ReportTab";
import { TodayTab } from "./TodayTab";

const PANELS: Record<CycleTabId, () => React.JSX.Element> = {
  today: TodayTab, calendar: CalendarTab, log: LogTab, insights: InsightsTab, fertility: FertilityTab, modes: ModesTab, report: ReportTab,
};

export function CycleTabs() {
  const [tab, setTab] = useState<CycleTabId>("today");
  const buttons = useRef<Partial<Record<CycleTabId, HTMLButtonElement | null>>>({});

  useEffect(() => {
    const sync = () => setTab(tabFromHash(window.location.hash));
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  const select = useCallback((id: CycleTabId, focus = false) => {
    setTab(id);
    window.history.replaceState(null, "", `#${id}`);
    if (focus) buttons.current[id]?.focus();
  }, []);

  const Panel = PANELS[tab];

  return (
    <>
      <div
        role="tablist"
        aria-label="Cycle sections"
        className="-mx-1 flex gap-1 overflow-x-auto rounded-full border border-line bg-surface p-1 print:hidden"
      >
        {CYCLE_TABS.map((t) => {
          const active = t.id === tab;
          return (
            <button
              key={t.id}
              ref={(el) => { buttons.current[t.id] = el; }}
              type="button"
              role="tab"
              id={`cycle-tab-${t.id}`}
              aria-selected={active}
              aria-controls={`cycle-panel-${t.id}`}
              tabIndex={active ? 0 : -1}
              onClick={() => select(t.id)}
              onKeyDown={(e) => {
                const next = tabForKey(t.id, e.key);
                if (next) {
                  e.preventDefault();
                  select(next, true);
                }
              }}
              className={`min-h-[44px] shrink-0 whitespace-nowrap rounded-full px-4 text-body-sm font-extrabold ${
                active ? "bg-bubbles-pink-ink text-white" : "text-ink-soft hover:bg-tint-pink hover:text-bubbles-pink-deep"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {CYCLE_TABS.map((t) => (
        <div key={t.id} role="tabpanel" id={`cycle-panel-${t.id}`} aria-labelledby={`cycle-tab-${t.id}`} hidden={t.id !== tab} className="mt-5">
          {t.id === tab && <Panel />}
        </div>
      ))}

      <LogButton />
    </>
  );
}

function LogButton() {
  const { openLog } = useCycle();
  return (
    <button
      type="button"
      aria-label="Log today"
      onClick={() => openLog()}
      className="bubbles-press fixed bottom-[calc(10.5rem+env(safe-area-inset-bottom))] right-4 z-[55] flex h-14 w-14 items-center justify-center rounded-full bg-bubbles-pink-ink text-white bubbles-glow print:hidden lg:bottom-28 lg:right-8"
    >
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" aria-hidden="true" focusable="false">
        <path d="M12 5v14M5 12h14" />
      </svg>
    </button>
  );
}
