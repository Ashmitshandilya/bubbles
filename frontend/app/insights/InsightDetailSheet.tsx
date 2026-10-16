"use client";

// One detail sheet for every insight (Patterns, links between what you log, Today). A native modal <dialog>, modelled on
// LogSheet in components/tracking/kit.tsx: the page behind is inert, Esc and a tap outside close it, the heading takes
// focus on open, and focus goes back to the button that opened it. Pure content lives in ./detail.ts.
import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { Icon } from "../../components/tracking/kit";
import { useApi } from "../../components/Providers";
import { fromApi, goneMessage, toDetail, type InsightDetail } from "./detail";

export interface SheetTarget {
  /** Server id for GET /insights/{id}; null when the card already carries everything. */
  id: string | null;
  /** Window the id is looked up in. */
  days: number;
  /** Ask the server for the days behind it (Today and `?item=`). Patterns and links already hold them. */
  fetch: boolean;
  /** What the card already knows. Null for a deep link, where the server is the only source. */
  base: InsightDetail | null;
}

type Remote =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; detail: InsightDetail }
  | { status: "gone" }
  | { status: "error" };

interface SheetApi {
  open: (target: SheetTarget, trigger: HTMLElement | null) => void;
}

const SheetContext = createContext<SheetApi | null>(null);

/** Wrap a screen once; every DetailsButton below it opens the same sheet. */
export function InsightSheetProvider({ children }: { children: ReactNode }) {
  const [target, setTarget] = useState<SheetTarget | null>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const api = useMemo<SheetApi>(
    () => ({
      open: (next, from) => {
        trigger.current = from;
        setTarget(next);
      },
    }),
    [],
  );
  const close = useCallback(() => {
    setTarget(null);
    const from = trigger.current;
    trigger.current = null;
    if (from?.isConnected) window.setTimeout(() => from.focus(), 0);
  }, []);

  return (
    <SheetContext.Provider value={api}>
      {children}
      <InsightDetailSheet target={target} onClose={close} />
    </SheetContext.Provider>
  );
}

export function useInsightSheet(): SheetApi | null {
  return useContext(SheetContext);
}

/** The visible word is "Details"; the accessible name carries the headline so every button on a page is unique. */
export function DetailsButton({ headline, target, className = "" }: { headline: string; target: () => SheetTarget; className?: string }) {
  const sheet = useInsightSheet();
  if (!sheet) return null;
  return (
    <button
      type="button"
      aria-haspopup="dialog"
      onClick={(event) => sheet.open(target(), event.currentTarget)}
      className={`bubbles-press inline-flex min-h-[44px] items-center gap-1.5 self-start rounded-full border border-line bg-surface px-4 text-sm font-extrabold text-bubbles-grape-deep hover:border-line-strong ${className}`}
    >
      Details
      <span className="sr-only"> about {headline}</span>
    </button>
  );
}

/** `?item=<id>` opens that insight once, then is removed from the address so a refresh does not reopen it. */
export function useOpenItemFromUrl(days: number) {
  const sheet = useInsightSheet();
  const openRef = useRef(sheet?.open);
  const daysRef = useRef(days);
  useEffect(() => {
    openRef.current = sheet?.open;
    daysRef.current = days;
  });
  useEffect(() => {
    const url = new URL(window.location.href);
    const id = url.searchParams.get("item");
    if (!id) return;
    url.searchParams.delete("item");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    openRef.current?.({ id, days: daysRef.current, fetch: true, base: null }, null);
  }, []);
}

const SECTION = "flex flex-col gap-1.5";
const H3 = "m-0 text-label font-extrabold text-muted";

function Numbers({ detail, remote, onRetry, days }: { detail: InsightDetail; remote: Remote; onRetry: () => void; days: number }) {
  if (remote.status === "loading") {
    return (
      <p role="status" className="m-0 text-body-sm font-semibold text-muted">
        Looking up the days behind this…
      </p>
    );
  }
  if (remote.status === "error") {
    return (
      <div className="flex flex-col items-start gap-2">
        <p role="alert" className="m-0 text-body-sm font-semibold text-muted">
          The days did not load just now.
        </p>
        <button type="button" onClick={onRetry} className="bubbles-press inline-flex min-h-[44px] items-center rounded-full border border-line px-4 text-sm font-extrabold text-bubbles-grape-deep">
          Try again
        </button>
      </div>
    );
  }
  if (remote.status === "gone") return <p className="m-0 text-body-sm text-ink">{goneMessage(days)}</p>;
  if ("gap" in detail.numbers) return <p className="m-0 text-body-sm text-ink">{detail.numbers.gap}</p>;
  const { caption, head, rows } = detail.numbers.table;
  return (
    <table data-private className="w-full border-collapse text-left text-body-sm">
      <caption className="pb-2 text-left text-body-sm font-semibold text-muted">{caption}</caption>
      <thead>
        <tr>
          {head.map((cellText) => (
            <th key={cellText} scope="col" className="border-b border-line px-1 py-2 font-extrabold text-ink">
              {cellText}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={`${row.join("|")}-${i}`}>
            {row.map((cellText, j) =>
              j === 0 ? (
                <th key={j} scope="row" className="border-b border-line px-1 py-2 font-semibold text-ink">
                  {cellText}
                </th>
              ) : (
                <td key={j} className="border-b border-line px-1 py-2 text-ink">
                  {cellText}
                </td>
              ),
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function InsightDetailSheet({ target, onClose }: { target: SheetTarget | null; onClose: () => void }) {
  const { fetchBubbles } = useApi();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const titleId = useId();
  const [remote, setRemote] = useState<Remote>({ status: "idle" });
  const [attempt, setAttempt] = useState(0);
  const fetchRef = useRef(fetchBubbles);
  useEffect(() => {
    fetchRef.current = fetchBubbles;
  });

  const open = target !== null;
  const wantsFetch = Boolean(target?.fetch && target.id);
  const id = target?.id ?? null;
  const days = target?.days ?? 30;

  // native dialog: modal, inert page behind, scroll lock, heading focus
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    const root = document.documentElement;
    const overflow = root.style.overflow;
    if (!dialog.open) dialog.showModal();
    root.style.overflow = "hidden";
    // preventScroll: the sheet slides up as it opens, and a plain focus() would scroll to where the heading is mid-animation
    headingRef.current?.focus({ preventScroll: true });
    dialog.scrollTop = 0;
    return () => {
      if (dialog.open) dialog.close();
      root.style.overflow = overflow;
    };
  }, [open]);

  useEffect(() => {
    if (!wantsFetch || !id) {
      setRemote({ status: "idle" });
      return;
    }
    let alive = true;
    setRemote({ status: "loading" });
    (async () => {
      try {
        const response = await fetchRef.current(`/insights/${encodeURIComponent(id)}?days=${days}`);
        if (!alive) return;
        if (response.status === 404) return setRemote({ status: "gone" });
        if (!response.ok) return setRemote({ status: "error" });
        const body = (await response.json()) as { insight?: unknown };
        const input = fromApi(body.insight, days);
        if (!alive) return;
        setRemote(input ? { status: "ready", detail: toDetail(input) } : { status: "gone" });
      } catch {
        if (alive) setRemote({ status: "error" });
      }
    })();
    return () => {
      alive = false;
    };
  }, [wantsFetch, id, days, attempt]);

  const detail = remote.status === "ready" ? remote.detail : (target?.base ?? null);
  const title = detail?.title ?? (remote.status === "gone" ? "Not in this window" : "Details");

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="m-0 mt-auto max-h-[94dvh] w-full max-w-none overflow-y-auto overscroll-contain bg-transparent p-0 text-default backdrop:bg-ink/55 sm:m-auto sm:w-[calc(100%-2rem)] sm:max-w-[600px]"
    >
      {open && (
        <div className="bubbles-sheet-up flex flex-col gap-5 rounded-t-[24px] bg-surface px-5 pb-[max(1.75rem,env(safe-area-inset-bottom))] pt-3 sm:rounded-[24px] sm:px-7 sm:pb-7 sm:pt-6">
          <span aria-hidden="true" className="mx-auto h-1.5 w-12 rounded-full bg-line sm:hidden" />
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              {detail && <p className="m-0 text-label font-extrabold text-bubbles-grape-deep">{detail.kindLabel}</p>}
              <h2 id={titleId} ref={headingRef} tabIndex={-1} data-private className="m-0 mt-1 font-display text-h3 text-default outline-none">
                {title}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close details"
              className="bubbles-press flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-line bg-surface text-muted hover:text-default"
            >
              <Icon name="close" size={20} />
            </button>
          </div>

          {!detail ? (
            remote.status === "gone" ? (
              <p className="m-0 text-body text-ink">{goneMessage(days)}</p>
            ) : remote.status === "error" ? (
              <div className="flex flex-col items-start gap-2">
                <p role="alert" className="m-0 text-body text-ink">
                  Bubbles could not load this just now.
                </p>
                <button type="button" onClick={() => setAttempt((n) => n + 1)} className="bubbles-press inline-flex min-h-[44px] items-center rounded-full border border-line px-4 text-sm font-extrabold text-bubbles-grape-deep">
                  Try again
                </button>
              </div>
            ) : (
              <p role="status" className="m-0 text-body text-muted">
                Looking this up…
              </p>
            )
          ) : (
            <>
              <section aria-labelledby={`${titleId}-saw`} className={SECTION}>
                <h3 id={`${titleId}-saw`} className={H3}>
                  What Bubbles saw
                </h3>
                <p data-private className="m-0 text-body text-ink">
                  {detail.saw}
                </p>
              </section>

              <section aria-labelledby={`${titleId}-numbers`} className={SECTION}>
                <h3 id={`${titleId}-numbers`} className={H3}>
                  The days and numbers
                </h3>
                <Numbers detail={detail} remote={remote} days={days} onRetry={() => setAttempt((n) => n + 1)} />
              </section>

              <section aria-labelledby={`${titleId}-sure`} className={SECTION}>
                <h3 id={`${titleId}-sure`} className={H3}>
                  How sure
                </h3>
                <p className="m-0 text-body text-ink">
                  <strong className="font-extrabold">{detail.sure.word}.</strong> {detail.sure.reason}
                </p>
              </section>

              <section aria-labelledby={`${titleId}-not`} className={SECTION}>
                <h3 id={`${titleId}-not`} className={H3}>
                  What this does not mean
                </h3>
                <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-body text-ink">
                  {detail.not.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </section>

              <section aria-labelledby={`${titleId}-try`} className={SECTION}>
                <h3 id={`${titleId}-try`} className={H3}>
                  One thing to try
                </h3>
                <p className="m-0 text-body text-ink">{detail.tryThis}</p>
              </section>

              <section aria-labelledby={`${titleId}-ask`} className={SECTION}>
                <h3 id={`${titleId}-ask`} className={H3}>
                  Ask Bubbles about it
                </h3>
                <Link
                  href={detail.ask.href}
                  className="bubbles-press inline-flex min-h-[48px] items-center self-start rounded-full bg-bubbles-grape px-5 text-sm font-extrabold text-white no-underline"
                >
                  {detail.ask.label}
                </Link>
              </section>
            </>
          )}
        </div>
      )}
    </dialog>
  );
}
