"use client";

import { useEffect, useRef, useState } from "react";
import { telHref, type Harbor } from "../lib/safe-harbor";

/**
 * A Safe Harbor reply: someone told Bubbles that a person close to them hurts or frightens them. Plain words only.
 * No mascot, no colour decoration, no card: just the text, one quiet button and the choices. The text is `data-private`, so the
 * Privacy veil blurs it like the rest of the chat. Nothing here is ever put in a title or a notification.
 */

const ring = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-bubbles-grape";

/** "People who can help": a quiet button that opens a sheet with every resource and a tap-to-call link. A link only, never an automatic call. */
export function HarborHelp({ harbor }: { harbor: Harbor }) {
  const [open, setOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        className={`bubbles-press inline-flex min-h-[44px] w-fit items-center rounded-full border border-line-strong bg-transparent px-4 text-body-sm font-extrabold text-ink hover:border-ink ${ring}`}
      >
        People who can help
      </button>
      <dialog
        ref={dialogRef}
        aria-labelledby="harbor-help-title"
        onClose={() => setOpen(false)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setOpen(false);
        }}
        className="mx-auto mb-0 mt-auto max-h-[88dvh] w-full max-w-none overflow-y-auto rounded-t-3xl border-0 bg-surface p-0 text-ink backdrop:bg-ink/40 sm:my-auto sm:max-w-md sm:rounded-3xl"
      >
        {open && (
          <div className="flex flex-col gap-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <h2 id="harbor-help-title" className="m-0 font-display text-h3 font-semibold">
                People who can help
              </h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close"
                className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-line text-ink ${ring}`}
              >
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
                  <path d="M6 6l12 12M18 6 6 18" />
                </svg>
              </button>
            </div>
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {harbor.resources.map((r, i) => {
                const href = telHref(r.number);
                return (
                  <li key={`${r.name}-${i}`} className="flex flex-col gap-2 border-t border-line pt-3 first:border-t-0 first:pt-0">
                    <div className="min-w-0">
                      <strong className="block break-words text-body font-extrabold">{r.name}</strong>
                      {r.note && <span className="block break-words text-body-sm text-ink-soft">{r.note}</span>}
                    </div>
                    {href && (
                      <a
                        href={href}
                        className={`bubbles-press inline-flex min-h-[48px] w-full items-center justify-center rounded-full bg-ink px-5 text-body font-extrabold text-blush no-underline ${ring}`}
                      >
                        Call {r.number}
                      </a>
                    )}
                  </li>
                );
              })}
            </ul>
            <p className="m-0 text-body-sm text-ink-soft">Nothing is dialled for you. You choose whether to call.</p>
          </div>
        )}
      </dialog>
    </>
  );
}

/** The follow-up choices (the words of each are sent as the next message; the server reads the choice from them). */
export function HarborChips({ labels, disabled, onPick }: { labels: string[]; disabled: boolean; onPick: (text: string) => void }) {
  if (labels.length === 0) return null;
  return (
    <div role="group" aria-label="What would help now" className="flex flex-wrap gap-2">
      {labels.map((label) => (
        <button
          key={label}
          type="button"
          disabled={disabled}
          onClick={() => onPick(label)}
          className={`bubbles-press min-h-[44px] max-w-full rounded-full border border-line-strong bg-transparent px-4 py-2 text-left text-body-sm font-extrabold text-ink hover:border-ink disabled:cursor-not-allowed disabled:opacity-60 ${ring}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
