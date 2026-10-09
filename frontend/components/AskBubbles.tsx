"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth, useApi } from "./Providers";
import { BubblesMascot } from "./BubblesMascot";
import { askHref } from "../app/lib/ask-handoff";

const FALLBACK_SUGGESTIONS = [
  "How's my sleep this week?",
  "What's affecting my energy?",
  "When's my next period?",
  "Summarize my health for my doctor",
  "Am I drinking enough water?",
  "How's my recovery trending?",
];

const chip =
  "min-h-[44px] rounded-full border-2 border-bubbles-grape/20 bg-surface px-3.5 text-left text-body-sm font-extrabold text-bubbles-grape-deep transition-colors hover:border-bubbles-grape";

/**
 * Floating quick-ask on every app page. A native modal <dialog> provides the
 * focus containment, Esc-to-close and focus return; questions open in /companion. Long text is handed over
 * through sessionStorage (see askHref) so health details never sit in the URL.
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
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

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

  useEffect(() => {
    if (session) {
      void loadSuggestions();
      void loadRecentQueries();
    }
  }, [session, loadSuggestions, loadRecentQueries]);

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

  function ask(text: string) {
    const question = text.trim();
    if (!question) return;
    setRecentQueries((prev) => [question, ...prev.filter((q) => q !== question)].slice(0, 4));
    setQuery("");
    setIsOpen(false);
    router.push(askHref(question));
  }

  // The Today dashboard has its own inline Ask Bubbles box, so the floating button would only cover content there.
  if (!session || pathname === "/dashboard") return null;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen(true)}
        aria-label="Ask Bubbles"
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        className="bubbles-ask-fab bubbles-press fixed bottom-[calc(6rem+env(safe-area-inset-bottom))] right-4 z-sticky flex h-16 items-center gap-2 rounded-full bg-bubbles-grape p-2 text-white shadow-[0_5px_0_var(--bubbles-grape-deep)] lg:bottom-6 lg:right-6 lg:pr-5"
      >
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-surface">
          <BubblesMascot size={40} />
        </span>
        <span className="hidden text-body font-extrabold lg:inline">Ask Bubbles</span>
      </button>

      <dialog
        ref={dialogRef}
        aria-labelledby="ask-bubbles-title"
        onClose={() => {
          setIsOpen(false);
          triggerRef.current?.focus();
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget) setIsOpen(false);
        }}
        className="mx-auto mb-0 mt-auto w-full max-w-none border-0 bg-transparent p-0 backdrop:bg-ink/40 sm:my-auto sm:w-[calc(100%-2rem)] sm:max-w-lg"
      >
        {isOpen && (
          <div className="bubbles-rise flex flex-col gap-4 rounded-t-[28px] border-2 border-line bg-surface px-5 pb-[max(20px,env(safe-area-inset-bottom))] pt-5 text-ink sm:rounded-[28px] sm:p-6">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <BubblesMascot size={48} />
                <div>
                  <h2 id="ask-bubbles-title" className="m-0 font-display text-h3 font-semibold">
                    Ask Bubbles
                  </h2>
                  <p className="m-0 text-body-sm text-ink-soft">Quick question? Bubbles answers in your chat.</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close"
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 border-line text-ink-soft hover:text-ink"
              >
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
                  <path d="M6 6l12 12M18 6 6 18" />
                </svg>
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                ask(query);
              }}
              className="flex flex-col gap-1.5"
            >
              <label htmlFor="ask-bubbles-input" className="text-body-sm font-extrabold">
                Your question
              </label>
              <div className="flex items-center gap-2 rounded-full border-2 border-ink bg-surface py-1.5 pl-4 pr-1.5 focus-within:border-bubbles-grape">
                <input
                  ref={inputRef}
                  id="ask-bubbles-input"
                  type="text"
                  value={query}
                  maxLength={8000}
                  autoComplete="off"
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g. How's my sleep this week?"
                  className="min-h-[44px] min-w-0 flex-1 border-0 bg-transparent text-body text-ink outline-none focus-visible:outline-none"
                />
                <button
                  type="submit"
                  disabled={!query.trim()}
                  className="bubbles-press min-h-[44px] shrink-0 rounded-full bg-bubbles-grape px-5 text-body-sm font-extrabold text-white shadow-[0_4px_0_var(--bubbles-grape-deep)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Ask
                </button>
              </div>
            </form>

            {recentQueries.length > 0 && (
              <div className="flex flex-col gap-2">
                <h3 className="m-0 text-label font-extrabold uppercase tracking-wide text-ink-soft">Recent</h3>
                <div className="flex flex-wrap gap-2">
                  {recentQueries.map((q) => (
                    <button key={q} type="button" onClick={() => ask(q)} className={chip}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

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

            <p className="m-0 text-[0.8125rem] font-bold text-ink-soft">Not a diagnosis · for emergencies call your local number</p>
          </div>
        )}
      </dialog>
    </>
  );
}
