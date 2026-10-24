"use client";

// The Patterns fold on Today. Loaded on demand (only when the fold is opened), so its code stays out of the first load.

import { Gap, Thread } from "../../../components/pearl";
import { DetailsButton } from "../../insights/InsightDetailSheet";
import { toDetail } from "../../insights/detail";
import { Icon } from "./TodaySections";
import { PATTERN_DAYS, type PatternItem } from "./today";

export function Patterns({ state, items, note, onRetry }: { state: "loading" | "error" | "ready"; items: PatternItem[]; note?: string; onRetry: () => void }) {
  return (
    <div>
      {state === "loading" && <Gap>Looking for patterns…</Gap>}
      {state === "error" && (
        <Gap>
          Bubbles couldn&apos;t load patterns right now. <button type="button" onClick={onRetry} className="pearl-link"><Icon name="refresh" size={14} /> Try again</button>
        </Gap>
      )}
      {state === "ready" && items.length === 0 && <Gap>Not enough data yet. Patterns show once you&apos;ve logged for a week or two.</Gap>}
      {state === "ready" && items.map((item) => (
        <div key={item.id} data-private>
          <Thread from="Noticed" to="In your logs" sentence={item.title} sure={item.pill.text} />
          {item.detail && <p className="pearl-note">{item.detail}</p>}
          <DetailsButton
            headline={item.title}
            target={() => ({ id: item.insightId ?? null, days: PATTERN_DAYS, fetch: Boolean(item.insightId), base: toDetail({ kind: "today", item: item.source }) })}
          />
        </div>
      ))}
      {note && <p className="pearl-note">{note}</p>}
    </div>
  );
}
