"use client";

// Education articles as an accordion. They are general knowledge, labelled as such, never read from the user's data.

import { useState } from "react";
import { PILL, useBubblesQuery } from "../hub/HubKit";
import type { Article, CycleMode, EducationResponse } from "../../app/lib/cycle-types";
import { Card, PanelError } from "./shared";

export function EducationSection({ mode, title, filter, emptyText }: { mode: CycleMode; title: string; filter?: (a: Article) => boolean; emptyText?: string }) {
  const [query, reload] = useBubblesQuery<EducationResponse>(`/cycle/education?mode=${encodeURIComponent(mode)}`);
  const [open, setOpen] = useState<string | null>(null);
  const articles = query.status === "ready" ? query.data.articles.filter(filter ?? (() => true)) : [];

  return (
    <Card labelledBy={`edu-${title}`}>
      <h3 id={`edu-${title}`} className="m-0 font-display text-h3 text-ink">{title}</h3>
      {query.status === "loading" && <p role="status" className="m-0 mt-2 text-body text-muted">Loading…</p>}
      {query.status === "error" && <div className="mt-3"><PanelError title="Articles didn't load" message={query.message} onRetry={reload} /></div>}
      {query.status === "ready" && articles.length === 0 && <p className="m-0 mt-2 text-body text-muted">{emptyText ?? "No articles for this mode yet."}</p>}
      <ul className="m-0 mt-3 list-none space-y-2 p-0">
        {articles.map((a) => {
          const expanded = open === a.id;
          return (
            <li key={a.id} className="rounded-2xl border-2 border-line">
              <h4 className="m-0">
                <button
                  type="button"
                  aria-expanded={expanded}
                  aria-controls={`art-${a.id}`}
                  onClick={() => setOpen(expanded ? null : a.id)}
                  className="flex min-h-[48px] w-full items-center justify-between gap-3 rounded-2xl px-4 py-2 text-left font-display text-h4 text-ink"
                >
                  <span>{a.title}</span>
                  <span aria-hidden="true" className="text-lg">{expanded ? "−" : "+"}</span>
                </button>
              </h4>
              <p className="m-0 px-4 pb-3"><span className={`${PILL} bg-tint-sky text-bubbles-sky-deep`}>{a.label}</span></p>
              <div id={`art-${a.id}`} hidden={!expanded} className="space-y-2 px-4 pb-4">
                <p className="m-0 text-body font-bold text-ink">{a.summary}</p>
                {a.body.map((p, i) => <p key={i} className="m-0 text-body text-ink">{p}</p>)}
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
