"use client";

import type { KeyboardEvent } from "react";
import { STATUS_META, STATUS_ORDER, countByStatus, type Organ } from "../../app/lib/organ-map";

const swatch = (status: Organ["status"]) =>
  status === "no_data"
    ? "border-2 border-dashed border-ink-faint bg-surface"
    : "";

/**
 * Every body part as a real button with its status in text: the screen-reader view of the body and the keyboard way
 * to move around it (Tab in, arrow keys between parts, Home and End to jump).
 */
export function OrganList({
  organs,
  selected,
  hovered,
  onSelect,
  onHover,
}: {
  organs: readonly Organ[];
  selected: string | null;
  hovered: string | null;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}) {
  const counts = countByStatus(organs);
  const withData = organs.length - counts.no_data;

  const onKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    const keys: Record<string, (i: number) => number> = {
      ArrowDown: (i) => (i + 1) % organs.length,
      ArrowRight: (i) => (i + 1) % organs.length,
      ArrowUp: (i) => (i - 1 + organs.length) % organs.length,
      ArrowLeft: (i) => (i - 1 + organs.length) % organs.length,
      Home: () => 0,
      End: () => organs.length - 1,
    };
    const move = keys[event.key];
    const current = (event.target as HTMLElement).closest<HTMLElement>("[data-organ]")?.dataset.organ;
    if (!move || !current) return;
    event.preventDefault();
    const next = organs[move(organs.findIndex((o) => o.id === current))];
    onSelect(next.id);
    event.currentTarget.querySelector<HTMLElement>(`[data-organ="${next.id}"]`)?.focus();
  };

  return (
    <section aria-labelledby="organ-list-title" className="rounded-3xl border-2 border-line bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="organ-list-title" className="text-h4 text-ink">
          Body parts
        </h2>
        <p className="text-caption text-muted">
          {withData} of {organs.length} with recent entries
        </p>
      </div>

      <ul className="m-0 mt-3 grid list-none grid-cols-1 gap-2 p-0 sm:grid-cols-2" onKeyDown={onKeyDown}>
        {organs.map((organ) => {
          const meta = STATUS_META[organ.status];
          const on = organ.id === selected;
          return (
            <li key={organ.id}>
              <button
                type="button"
                data-organ={organ.id}
                aria-pressed={on}
                onClick={() => onSelect(organ.id)}
                onPointerEnter={() => onHover(organ.id)}
                onPointerLeave={() => onHover(null)}
                className={`flex min-h-[52px] w-full items-center gap-3 rounded-2xl border-2 px-3.5 py-2 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-bubbles-grape ${
                  on ? "border-ink bg-blush" : hovered === organ.id ? "border-line-strong bg-blush" : "border-line bg-surface hover:border-line-strong"
                }`}
              >
                <span
                  className={`h-3 w-3 shrink-0 rounded-full ${swatch(organ.status)}`}
                  style={organ.status === "no_data" ? undefined : { background: `var(${meta.color})` }}
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1">
                  <span className="block font-extrabold text-ink">{organ.name}</span>
                  <span className="block text-caption text-muted">{meta.label}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <StatusLegend />
    </section>
  );
}

export function StatusLegend() {
  return (
    <div className="mt-5 border-t border-line pt-4">
      <h3 className="text-body-sm font-extrabold text-ink">What the colours mean</h3>
      <dl className="mt-2 grid gap-2 sm:grid-cols-2">
        {STATUS_ORDER.map((status) => {
          const meta = STATUS_META[status];
          return (
            <div key={status} className="flex gap-2.5">
              <span
                className={`mt-1 h-3 w-3 shrink-0 rounded-full ${swatch(status)}`}
                style={status === "no_data" ? undefined : { background: `var(${meta.color})` }}
                aria-hidden="true"
              />
              <div>
                <dt className="text-body-sm font-bold text-ink">{meta.label}</dt>
                <dd className="text-caption text-muted">{meta.meaning}</dd>
              </div>
            </div>
          );
        })}
      </dl>
    </div>
  );
}
