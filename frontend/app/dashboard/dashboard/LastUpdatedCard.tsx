"use client";

import { useEffect, useState } from "react";
import { agoText, type LastUpdate } from "../../lib/data-sync";

/** What the person changed most recently, and when. Hidden until something has been saved. */
export function LastUpdatedCard({ update }: { update: LastUpdate | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  if (!update) return null;
  return (
    <section aria-label="Last updated" className="flex items-center justify-between gap-3 border-t border-[color:var(--hairline)] py-4">
      <div className="min-w-0">
        <p className="m-0 text-chip font-semibold uppercase tracking-wide text-ink-soft">Last updated</p>
        <p className="m-0 truncate text-body font-bold">{update.label}</p>
      </div>
      <p className="m-0 shrink-0 text-chip font-semibold text-ink-soft">{agoText(update.at, now)}</p>
    </section>
  );
}
