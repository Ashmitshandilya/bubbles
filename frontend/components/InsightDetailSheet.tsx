"use client";

// One native <dialog> for every insight. Focus goes to the heading on open and back to the button that opened it, Esc, the
// backdrop and the Close button all close it, and the page behind does not scroll. Android back closes `dialog[open]` already.

import Link from "next/link";
import { useEffect, useId, useRef } from "react";
import type { InsightDetail } from "../app/insights/detail";
import { BTN_SECONDARY, PILL } from "./hub/HubKit";

const H = "m-0 mb-1 text-body font-extrabold text-ink";

export function InsightDetailSheet({ detail, onClose }: { detail: InsightDetail | null; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const titleId = useId();
  const open = detail !== null;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const root = document.documentElement;
    const overflow = root.style.overflow;
    if (!dialog.open) dialog.showModal();
    root.style.overflow = "hidden";
    headingRef.current?.focus();
    return () => {
      if (dialog.open) dialog.close();
      root.style.overflow = overflow;
      trigger?.focus();
    };
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="m-0 mt-auto max-h-[94dvh] w-full max-w-none overflow-y-auto overscroll-contain bg-transparent p-0 text-default backdrop:bg-ink/55 sm:m-auto sm:w-[calc(100%-2rem)] sm:max-w-[560px]"
    >
      {detail && (
        <div className="bubbles-sheet-up flex flex-col gap-5 rounded-t-[24px] bg-surface px-5 pb-[max(1.75rem,env(safe-area-inset-bottom))] pt-4 sm:rounded-[24px] sm:px-7 sm:pb-7 sm:pt-6">
          <h2 id={titleId} ref={headingRef} tabIndex={-1} className="m-0 font-display text-h3 text-ink outline-none">{detail.title}</h2>

          <section aria-label="What Bubbles saw">
            <h3 className={H}>What Bubbles saw</h3>
            <p className="m-0 text-body-sm text-ink-soft">{detail.saw}</p>
          </section>

          <section aria-label="The days and numbers">
            <h3 className={H}>The days and numbers</h3>
            {detail.table ? (
              <table className="w-full border-collapse text-left text-body-sm text-ink-soft">
                <caption className="sr-only">{detail.table.caption}</caption>
                {detail.table.head.length > 1 && (
                  <thead><tr>{detail.table.head.map((h) => <th key={h} scope="col" className="border-b border-line py-1 pr-3 font-extrabold text-ink">{h}</th>)}</tr></thead>
                )}
                <tbody>
                  {detail.table.rows.map((row, i) => (
                    <tr key={i}>{row.map((cell, j) => (j === 0 && row.length > 1
                      ? <th key={j} scope="row" className="border-b border-line py-1.5 pr-3 font-bold text-ink">{cell}</th>
                      : <td key={j} className="border-b border-line py-1.5">{cell}</td>))}</tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="m-0 text-body-sm text-muted">{detail.gap}</p>
            )}
          </section>

          <section aria-label="How sure">
            <h3 className={H}>How sure</h3>
            <p className="m-0 text-body-sm text-ink-soft"><span className={`${PILL} mr-2 bg-tint-grape text-bubbles-grape-deep`}>{detail.how.word}</span>{detail.how.reason}</p>
          </section>

          <section aria-label="What this does not mean">
            <h3 className={H}>What this does not mean</h3>
            <ul className="m-0 list-disc space-y-1 pl-5 text-body-sm text-ink-soft">{detail.not.map((line) => <li key={line}>{line}</li>)}</ul>
          </section>

          <section aria-label="One thing to try">
            <h3 className={H}>One thing to try</h3>
            <p className="m-0 text-body-sm text-ink-soft">{detail.tryThis}</p>
          </section>

          <div className="flex flex-wrap gap-3">
            <Link href={`/companion?ask=${encodeURIComponent(detail.ask)}`} className={BTN_SECONDARY}>Ask Bubbles about it</Link>
            <button type="button" onClick={onClose} className={`${BTN_SECONDARY} min-h-[44px]`}>Close</button>
          </div>
        </div>
      )}
    </dialog>
  );
}
