"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth, useApi, useExperience } from "./Providers";
import { BubblesMascot } from "./BubblesMascot";
import { askHref } from "../app/lib/ask-handoff";
import { ME, SECTIONS } from "./Navigation";
import { filterSections } from "../app/lib/experience";
import { buildItems, buildRows, loadRecents, recordRecent, type PaletteRow } from "./commandPalette";

const FALLBACK_SUGGESTIONS = [
  "How's my sleep this week?",
  "What's affecting my energy?",
  "When's my next period?",
  "Summarize my health for my doctor",
  "Am I drinking enough water?",
  "How's my recovery trending?",
];

const chip =
  "min-h-[44px] rounded-full border border-bubbles-grape/20 bg-surface px-3.5 text-left text-body-sm font-extrabold text-bubbles-grape-deep transition-colors hover:border-bubbles-grape";

/**
 * "Ask or jump": a keyboard-first command palette on every app page (Ctrl+K or Cmd+K, or the floating button).
 * Typing filters pages and quick actions; free text still asks Bubbles in /companion. A native modal <dialog>
 * provides focus containment and Esc-to-close. Long questions are handed over through sessionStorage (see
 * askHref) so health details never sit in the URL. Only route ids are remembered, never what was typed.
 */
export function AskBubbles() {
  const router = useRouter();
  const pathname = usePathname();
  const { session } = useAuth();
  const { fetchBubbles } = useApi();
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>(FALLBACK_SUGGESTIONS);
  const [recentQueries, setRecentQueries] = useState<string[]>([]);
  const [recentIds, setRecentIds] = useState<string[]>([]);
  const [active, setActive] = useState(0);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const listId = useId();

  const { experience } = useExperience();
  const items = useMemo(() => buildItems([...filterSections(SECTIONS, experience), ME]), [experience]);
  const rows = useMemo(() => buildRows(items, query, recentIds), [items, query, recentIds]);
  const activeIndex = Math.min(active, rows.length - 1);
  const optionId = (i: number) => `${listId}-opt-${i}`;

  const openPalette = useCallback(() => {
    openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setRecentIds(loadRecents());
    setQuery("");
    setActive(0);
    setIsOpen(true);
  }, []);

  const loadSuggestions = useCallback(async () => {
    try {
      const response = await fetchBubbles("/intelligence/suggestions?limit=6");
      const data = response.ok ? await response.json() : null;
      setSuggestions(Array.isArray(data?.suggestions) && data.suggestions.length ? data.suggestions : FALLBACK_SUGGESTIONS);
    } catch {
      setSuggestions(FALLBACK_SUGGESTIONS);
    }
  }, [fetchBubbles]);

  const loadRecentQueries = useCallback(async () => {
    try {
      const response = await fetchBubbles("/intelligence/recent-queries?limit=4");
      if (response.ok) {
        const data = await response.json();
        setRecentQueries(Array.isArray(data?.queries) ? data.queries : []);
      }
    } catch {
      // Recent questions are a convenience; the suggestions still work without them.
    }
  }, [fetchBubbles]);

  // Asked when the palette is opened (not on every page load): they are only shown there. Not again within a minute of the last ask.
  const askedAt = useRef(0);
  useEffect(() => {
    if (!isOpen || !session || Date.now() - askedAt.current < 60_000) return;
    askedAt.current = Date.now();
    void loadSuggestions();
    void loadRecentQueries();
  }, [isOpen, session, loadSuggestions, loadRecentQueries]);

  // No cleanup that closes the dialog: under StrictMode the async `close` event would re-close it.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen) {
      if (!dialog.open) dialog.showModal();
      inputRef.current?.focus();
    } else if (dialog.open) {
      dialog.close();
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [isOpen]);

  // Ctrl+K / Cmd+K toggles the palette from anywhere in the app (not while another dialog, like the menu sheet, is open).
  useEffect(() => {
    if (!session) return;
    function onKeyDown(e: KeyboardEvent) {
      if (!(e.ctrlKey || e.metaKey) || e.altKey || e.key.toLowerCase() !== "k") return;
      const other = document.querySelector("dialog[open]");
      if (other && other !== dialogRef.current) return;
      e.preventDefault();
      if (isOpen) setIsOpen(false);
      else openPalette();
    }
    document.addEventListener("keydown", onKeyDown);
    // On phones the trigger is the header's search button (Navigation.tsx), which sends this event.
    window.addEventListener("bubbles:ask", openPalette);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("bubbles:ask", openPalette);
    };
  }, [session, isOpen, openPalette]);

  // Keep the highlighted row in view while arrowing through a long list.
  useEffect(() => {
    if (isOpen) document.getElementById(`${listId}-opt-${activeIndex}`)?.scrollIntoView({ block: "nearest" });
  }, [isOpen, activeIndex, listId, rows]);

  function ask(text: string) {
    const question = text.trim();
    if (!question) return;
    setRecentQueries((prev) => [question, ...prev.filter((q) => q !== question)].slice(0, 4));
    setQuery("");
    setIsOpen(false);
    router.push(askHref(question));
  }

  function activate(row: PaletteRow | undefined) {
    if (!row) return;
    if (row.kind === "ask") return ask(row.question);
    setRecentIds(recordRecent(row.id, items));
    setQuery("");
    setIsOpen(false);
    router.push(row.href);
  }

  function onInputKeyDown(e: ReactKeyboardEvent<HTMLInputElement>) {
    const el = e.currentTarget;
    const atStart = el.selectionStart === 0 && el.selectionEnd === 0;
    const atEnd = el.selectionStart === el.value.length && el.selectionEnd === el.value.length;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActive((activeIndex + 1) % rows.length);
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((activeIndex - 1 + rows.length) % rows.length);
        break;
      // Home/End jump the list only when the caret has nowhere to go, so editing a long question still works.
      case "Home":
        if (atStart) {
          e.preventDefault();
          setActive(0);
        }
        break;
      case "End":
        if (atEnd) {
          e.preventDefault();
          setActive(rows.length - 1);
        }
        break;
      case "Enter":
        if (e.nativeEvent.isComposing) break;
        e.preventDefault();
        activate(rows[activeIndex]);
        break;
    }
  }

  if (!session) return null;

  const pages = rows.filter((r) => r.kind !== "ask").length;
  const hasAsk = rows[0]?.kind === "ask";
  const status = !query.trim()
    ? `${pages} shortcuts`
    : pages === 0
      ? "No matching pages. Press Enter to ask Bubbles."
      : `${pages} ${pages === 1 ? "page" : "pages"}${hasAsk ? ", or ask Bubbles" : ""}`;

  return (
    <>
      {/* Large screens only: on phones a floating button sat over content and next to the tab bar's Talk button, so the
          header's search button opens the palette there instead. Today and the body map have their own Ask Bubbles buttons. */}
      {pathname !== "/dashboard" && pathname !== "/body" && (
        <button
          ref={triggerRef}
          type="button"
          onClick={openPalette}
          aria-label="Ask Bubbles"
          aria-haspopup="dialog"
          aria-keyshortcuts="Control+K Meta+K"
          aria-expanded={isOpen}
          className="bubbles-ask-fab bubbles-press fixed bottom-6 right-6 z-sticky hidden h-16 items-center gap-2 rounded-full bg-bubbles-grape p-2 pr-5 text-white bubbles-glow bubbles-glow-grape lg:flex"
        >
          <span className="flex h-12 w-12 items-center justify-center rounded-full" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 15a3 3 0 0 1-3 3H8l-4 3V6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3z" /></svg>
          </span>
          <span className="hidden text-[0.9375rem] font-semibold lg:inline">Ask Bubbles</span>
        </button>
      )}

      <dialog
        ref={dialogRef}
        aria-labelledby="ask-bubbles-title"
        onClose={() => {
          setIsOpen(false);
          (openerRef.current?.isConnected ? openerRef.current : triggerRef.current)?.focus();
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget) setIsOpen(false);
        }}
        className="mx-auto mb-0 mt-auto w-full max-w-none border-0 bg-transparent p-0 backdrop:bg-ink/40 sm:my-auto sm:w-[calc(100%-2rem)] sm:max-w-lg"
      >
        {isOpen && (
          <div className="bubbles-rise flex flex-col gap-4 rounded-t-[24px] border border-line bg-surface px-5 pb-[max(20px,env(safe-area-inset-bottom))] pt-5 text-ink sm:rounded-[24px] sm:p-6">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <BubblesMascot size={48} />
                <div>
                  <h2 id="ask-bubbles-title" className="m-0 font-display text-h3 font-semibold">
                    Ask or jump
                  </h2>
                  <p className="m-0 text-body-sm text-ink-soft">
                    Find a page, or ask Bubbles. <span className="hidden sm:inline">Shortcut: Ctrl K or Cmd K.</span>
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close"
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-line text-ink-soft hover:text-ink"
              >
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
                  <path d="M6 6l12 12M18 6 6 18" />
                </svg>
              </button>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="ask-bubbles-input" className="text-body-sm font-extrabold">
                Search pages or ask a question
              </label>
              <div className="flex items-center gap-2 rounded-full border border-line-strong bg-surface py-1.5 pl-4 pr-1.5 focus-within:border-bubbles-grape">
                <input
                  ref={inputRef}
                  id="ask-bubbles-input"
                  type="text"
                  role="combobox"
                  aria-expanded="true"
                  aria-controls={listId}
                  aria-autocomplete="list"
                  aria-activedescendant={rows.length ? optionId(activeIndex) : undefined}
                  value={query}
                  maxLength={8000}
                  autoComplete="off"
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setActive(0);
                  }}
                  onKeyDown={onInputKeyDown}
                  placeholder="e.g. sleep, log water, or How's my sleep this week?"
                  className="min-h-[44px] min-w-0 flex-1 border-0 bg-transparent text-body text-ink outline-none focus-visible:outline-none"
                />
                <button
                  type="button"
                  onClick={() => ask(query)}
                  disabled={!query.trim()}
                  className="bubbles-press min-h-[44px] shrink-0 rounded-full bg-bubbles-grape px-5 text-body-sm font-extrabold text-white bubbles-glow bubbles-glow-grape disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Ask
                </button>
              </div>
            </div>

            <div role="status" aria-live="polite" className="sr-only">
              {status}
            </div>
            <ul
              id={listId}
              role="listbox"
              aria-label={query.trim() ? "Results" : "Shortcuts"}
              className="m-0 flex max-h-[min(38dvh,19rem)] list-none flex-col gap-1 overflow-y-auto overscroll-contain p-0"
            >
              {rows.map((row, i) => (
                <li
                  key={row.id}
                  id={optionId(i)}
                  role="option"
                  aria-selected={i === activeIndex}
                  onMouseMove={() => i !== activeIndex && setActive(i)}
                  onClick={() => activate(row)}
                  className={`flex min-h-[44px] cursor-pointer items-center justify-between gap-3 rounded-2xl px-3 text-body-sm font-extrabold ${
                    i === activeIndex ? "bg-tint-pink text-bubbles-pink-ink outline outline-2 -outline-offset-2 outline-bubbles-grape" : "text-ink"
                  }`}
                >
                  <span className="min-w-0 truncate">{row.label}</span>
                  <span className="shrink-0 text-label font-bold text-ink-soft">{row.hint}</span>
                </li>
              ))}
            </ul>

            {!query.trim() && recentQueries.length > 0 && (
              <div className="flex flex-col gap-2">
                <h3 className="m-0 text-label font-extrabold uppercase tracking-wide text-ink-soft">Recent questions</h3>
                <div className="flex flex-wrap gap-2">
                  {recentQueries.map((q) => (
                    <button key={q} type="button" onClick={() => ask(q)} className={chip}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {!query.trim() && (
              <div className="flex flex-col gap-2">
                <h3 className="m-0 text-label font-extrabold uppercase tracking-wide text-ink-soft">Try asking</h3>
                <div className="flex flex-wrap gap-2">
                  {suggestions.slice(0, 6).map((s) => (
                    <button key={s} type="button" onClick={() => ask(s)} className={chip}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <p className="m-0 text-chip font-bold text-ink-soft">Not a diagnosis · for emergencies call your local number</p>
          </div>
        )}
      </dialog>
    </>
  );
}
