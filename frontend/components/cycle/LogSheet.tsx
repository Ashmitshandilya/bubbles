"use client";

// The floating "Log" sheet: a native modal <dialog> (focus trapped, Esc closes, background inert), a bottom sheet on
// phones and a centred dialog from 640px. Focus returns to the opener (the provider restores it) and page scroll locks.

import { useEffect, useId, useRef } from "react";
import { DayEditor } from "./DayEditor";

export function LogSheet({ open, date, onDateChange, onClose }: { open: boolean; date: string; onDateChange: (date: string) => void; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    const root = document.documentElement;
    const overflow = root.style.overflow;
    if (!dialog.open) dialog.showModal();
    root.style.overflow = "hidden";
    headingRef.current?.focus();
    return () => {
      if (dialog.open) dialog.close();
      root.style.overflow = overflow;
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
      className="m-0 mt-auto max-h-[94dvh] w-full max-w-none overflow-y-auto overscroll-contain bg-transparent p-0 text-default backdrop:bg-ink/55 sm:m-auto sm:w-[calc(100%-2rem)] sm:max-w-[640px] print:hidden"
    >
      {open && (
        <div className="bubbles-sheet-up flex flex-col gap-5 rounded-t-[24px] bg-surface px-5 pb-[max(1.75rem,env(safe-area-inset-bottom))] pt-3 sm:rounded-[24px] sm:px-7 sm:pb-7 sm:pt-6">
          <span aria-hidden="true" className="mx-auto h-1.5 w-12 rounded-full bg-line sm:hidden" />
          <div className="flex items-center gap-3">
            <h2 id={titleId} ref={headingRef} tabIndex={-1} className="m-0 min-w-0 flex-1 font-display text-h2 text-default outline-none">
              Log your day
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="bubbles-press flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-line bg-surface text-lg text-muted hover:text-default"
            >
              <span aria-hidden="true">×</span>
            </button>
          </div>
          <DayEditor date={date} onDateChange={onDateChange} onDone={onClose} />
        </div>
      )}
    </dialog>
  );
}
