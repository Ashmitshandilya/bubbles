"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AskBubbles } from "./AskBubbles";
import { NotificationBell } from "./wellness/NotificationBell";
import { BubblesMascot } from "./BubblesMascot";
import { useApi } from "./Providers";
import { connectionBanner, reconnectStatus } from "../app/lib/connection";

// Stroke-based 24x24 icon paths. One consistent set instead of platform-dependent
// emoji, which render at different sizes and colors per OS.
const ICON_PATHS: Record<string, string> = {
  dashboard: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  health: "M20.8 5.6a5 5 0 0 0-7.1 0L12 7.3l-1.7-1.7a5 5 0 1 0-7.1 7.1L12 21.5l8.8-8.8a5 5 0 0 0 0-7.1z",
  activity: "M3 12h4l3-8 4 16 3-8h4",
  companion: "M20 15a3 3 0 0 1-3 3H8l-4 3V6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3z",
  care: "M9 3h6v4h4v6h-4v4H9v-4H5V7h4z",
  cycle: "M20 11a8 8 0 1 0-1.5 5.5M20 4v7h-7",
  symptoms: "M12 4 2.5 20h19L12 4zM12 10v4M12 17.3v.1",
  sleep: "M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z",
  hydration: "M12 3s6 6.5 6 10.5a6 6 0 0 1-12 0C6 9.5 12 3 12 3z",
  nutrition: "M12 8C12 5 14.5 3 17.5 3c0 3-2.5 5-5.5 5zM12 8C12 5 9.5 3 6.5 3c0 3 2.5 5 5.5 5zM12 8C8.5 8 6 10.5 6 14.5S9 21 12 21s6-2.5 6-6.5S15.5 8 12 8z",
  mood: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8.5 14a4.5 4.5 0 0 0 7 0M9 9.5v.1M15 9.5v.1",
  weight: "M4 8h16l-1.5 12h-13zM12 8V5.5M9.5 5.5h5",
  vitals: "M4 4h16v16H4zM7.5 12h2l1.5-3.5L13 15l1.5-3h2",
  insights: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  medications: "M10.5 20.5a5 5 0 0 1-7-7l7-7a5 5 0 0 1 7 7zM8.5 8.5l7 7",
  conditions: "M9 4h6v3H9zM7 5H5v16h14V5h-2",
  allergies: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM5.6 5.6l12.8 12.8",
  labs: "M9 3v6l-4.5 8A2 2 0 0 0 6.2 20h11.6a2 2 0 0 0 1.7-3L15 9V3M8 3h8M7.5 14h9",
  reports: "M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6",
  visits: "M4 21V8l8-5 8 5v13M9 21v-6h6v6",
  profile: "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 21a7 7 0 0 1 14 0",
  fitness: "M6.5 6.5v11M17.5 6.5v11M3.5 9v6M20.5 9v6M6.5 12h11",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  settings: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1",
};

function NavIcon({ id, size = 18 }: { id: string; size?: number }) {
  const d = ICON_PATHS[id];
  if (!d) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={d} />
    </svg>
  );
}

type NavItem = {
  id: string;
  /** Icon key in ICON_PATHS (defaults to the id). */
  icon?: string;
  label: string;
  href: string;
  /** A link shown indented under the item above it. */
  sub?: boolean;
  /** Active only on this exact path (a hub whose children have their own links). */
  exact?: boolean;
};

const NAV_ITEMS: readonly NavItem[] = [
  { id: "dashboard", label: "Today", href: "/dashboard" },
  { id: "companion", label: "Talk to Bubbles", href: "/companion" },
  { id: "insights", label: "Patterns", href: "/insights" },
  { id: "health", label: "My health", href: "/health" },
  { id: "fitness", label: "Fitness", href: "/fitness", exact: true },
  { id: "fitness-diet", icon: "nutrition", label: "Diet", href: "/fitness/diet", sub: true },
  { id: "fitness-workouts", icon: "activity", label: "Workouts", href: "/fitness/workouts", sub: true },
  { id: "fitness-calories", icon: "nutrition", label: "Calories", href: "/fitness/calories", sub: true },
  { id: "fitness-transform", icon: "insights", label: "Transform", href: "/fitness/transform", sub: true },
  { id: "fitness-progress", icon: "weight", label: "Progress", href: "/fitness/progress", sub: true },
  { id: "nutrition", label: "Food log", href: "/nutrition", sub: true },
  { id: "weight", label: "Weight", href: "/weight", sub: true },
  { id: "activity", label: "Activity", href: "/activity", sub: true },
  { id: "cycle", label: "Cycle", href: "/cycle" },
  { id: "sleep", label: "Sleep", href: "/sleep" },
  { id: "hydration", label: "Water", href: "/hydration" },
  { id: "mood", label: "Mood", href: "/mood" },
  { id: "symptoms", label: "Symptoms", href: "/symptoms" },
  { id: "vitals", label: "Vitals", href: "/vitals" },
  { id: "care", label: "Doctor prep", href: "/care" },
  { id: "partner", label: "Partner sharing", href: "/partner" },
  { id: "medications", label: "Medications", href: "/medications" },
  { id: "conditions", label: "Conditions", href: "/conditions" },
  { id: "allergies", label: "Allergies", href: "/allergies" },
  { id: "labs", label: "Lab results", href: "/labs" },
  { id: "reports", label: "Reports", href: "/reports" },
  { id: "visits", label: "Visits", href: "/visits" },
  { id: "profile", label: "Me", href: "/profile" },
  { id: "settings", label: "Settings", href: "/settings" },
];

const NAV_GROUPS: readonly { label: string; items: readonly string[] }[] = [
  { label: "Bubbles", items: ["dashboard", "companion", "insights", "health"] },
  { label: "Fitness", items: ["fitness", "fitness-diet", "fitness-workouts", "fitness-calories", "fitness-transform", "fitness-progress", "nutrition", "weight", "activity"] },
  { label: "Cycle", items: ["cycle"] },
  { label: "Track", items: ["sleep", "hydration", "mood", "symptoms", "vitals"] },
  { label: "Care", items: ["care", "medications", "conditions", "allergies", "labs", "reports", "visits"] },
  { label: "You", items: ["profile", "settings"] },
];

function isActive(pathname: string, href: string, exact = false) {
  return pathname === href || (!exact && pathname.startsWith(`${href}/`));
}

function itemActive(pathname: string, item: NavItem) {
  return isActive(pathname, item.href, item.exact);
}

function StatusLine({ apiStatus }: { apiStatus: "checking" | "online" | "offline" }) {
  const label = apiStatus === "online" ? "Bubbles is here" : apiStatus === "offline" ? "Can't reach Bubbles" : "Connecting…";
  const dot = apiStatus === "online" ? "bg-bubbles-mint" : apiStatus === "offline" ? "bg-bubbles-urgent" : "bg-bubbles-sun";
  return (
    <span className="inline-flex items-center gap-2 text-body-sm font-bold text-muted" role="status">
      <span className={`h-2.5 w-2.5 rounded-full ${dot}`} aria-hidden="true" />
      {label}
    </span>
  );
}

export function Sidebar({ apiStatus }: { apiStatus: "checking" | "online" | "offline" }) {
  const pathname = usePathname() ?? "";

  return (
    <aside className="hidden lg:flex w-[248px] shrink-0 border-r border-soft bg-surface min-h-screen flex-col sticky top-0 h-dvh" aria-label="Bubbles navigation">
      <Link href="/dashboard" className="flex items-center gap-3 px-5 pt-5 pb-4 no-underline text-default">
        <BubblesMascot size={40} animated={false} />
        <span className="font-display text-[1.625rem] font-bold tracking-tight">bubbles</span>
      </Link>
      <nav className="flex-1 overflow-y-auto px-3 pb-4" style={{ scrollbarWidth: "thin" }}>
        {NAV_GROUPS.map((group) => (
          <div className="mb-5" key={group.label}>
            <span className="block px-3 pb-2 text-label font-extrabold uppercase tracking-wide text-subtle">{group.label}</span>
            <ul className="m-0 flex list-none flex-col gap-1 p-0">
              {group.items.map((id) => {
                const item = NAV_ITEMS.find((entry) => entry.id === id);
                if (!item) return null;
                const active = itemActive(pathname, item);
                return (
                  <li key={item.id} className={item.sub ? "ml-5 border-l-2 border-line pl-2" : undefined}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`flex min-h-[44px] items-center gap-3 rounded-2xl px-3 font-extrabold no-underline transition-colors ${
                        item.sub ? "text-body-sm" : "text-nav"
                      } ${active ? "bg-tint-pink text-bubbles-pink-ink" : "text-muted hover:bg-blush hover:text-default"}`}
                    >
                      {!item.sub && <NavIcon id={item.icon ?? item.id} size={20} />}
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t border-soft px-5 py-4">
        <StatusLine apiStatus={apiStatus} />
      </div>
    </aside>
  );
}

const MOBILE_TABS = [
  { id: "dashboard", label: "Today", href: "/dashboard" },
  { id: "fitness", label: "Fitness", href: "/fitness" },
  { id: "companion", label: "Talk", href: "/companion" },
  { id: "cycle", label: "Cycle", href: "/cycle" },
] as const;

/**
 * "More" sheet: every group and link. A native modal dialog, so the browser traps focus, Escape closes it,
 * the page behind is inert and focus returns to the More button. Links are 44px tall.
 */
function MoreSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const pathname = usePathname() ?? "";

  useEffect(() => {
    const dialog = ref.current;
    if (!open || !dialog) return;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const root = document.documentElement;
    const overflow = root.style.overflow;
    if (!dialog.open) dialog.showModal();
    root.style.overflow = "hidden";
    heading.current?.focus({ preventScroll: true });
    dialog.scrollTop = 0;
    return () => {
      if (dialog.open) dialog.close();
      root.style.overflow = overflow;
      trigger?.focus();
    };
  }, [open]);

  // Following a link closes the sheet.
  const lastPath = useRef(pathname);
  useEffect(() => {
    if (lastPath.current !== pathname) {
      lastPath.current = pathname;
      onClose();
    }
  }, [pathname, onClose]);

  return (
    <dialog
      ref={ref}
      aria-labelledby="more-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="m-0 mt-auto max-h-[92dvh] w-full max-w-none overflow-y-auto overscroll-contain bg-transparent p-0 text-default backdrop:bg-ink/55"
    >
      {open && (
        <div className="bubbles-sheet-up rounded-t-[36px] bg-surface px-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h2 id="more-title" ref={heading} tabIndex={-1} className="m-0 font-display text-h2 outline-none">
              Everything in Bubbles
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="bubbles-press flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 border-line bg-surface text-muted"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </div>
          {NAV_GROUPS.map((group) => (
            <section key={group.label} aria-label={group.label} className="mb-3">
              <h3 className="m-0 px-1 pb-1 text-label font-extrabold uppercase tracking-wide text-subtle">{group.label}</h3>
              <ul className="m-0 grid list-none grid-cols-2 gap-1 p-0">
                {group.items.map((id) => {
                  const item = NAV_ITEMS.find((entry) => entry.id === id);
                  if (!item) return null;
                  const active = itemActive(pathname, item);
                  return (
                    <li key={item.id}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={`flex min-h-[44px] items-center gap-2 rounded-2xl px-3 text-body-sm font-extrabold no-underline ${
                          active ? "bg-tint-pink text-bubbles-pink-ink" : "text-default hover:bg-blush"
                        }`}
                      >
                        <NavIcon id={item.icon ?? item.id} size={18} />
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      )}
    </dialog>
  );
}

/**
 * Bottom tab bar for phones: Today, Fitness, Talk (centre), Cycle, More. `activeView`/`onNavigate` are accepted for
 * backward compatibility; navigation uses real links and the current URL.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function MobileNav(_props: { activeView?: string; onNavigate?: (id: string) => void } = {}) {
  const pathname = usePathname() ?? "";
  const [moreOpen, setMoreOpen] = useState(false);
  const closeMore = useCallback(() => setMoreOpen(false), []);
  const onTab = MOBILE_TABS.some((tab) => isActive(pathname, tab.href));
  const tabLink = (item: (typeof MOBILE_TABS)[number]) => {
    const active = isActive(pathname, item.href);
    return (
      <li key={item.id}>
        <Link
          href={item.href}
          aria-current={active ? "page" : undefined}
          className={`flex min-h-[48px] min-w-[56px] flex-col items-center justify-center gap-0.5 rounded-2xl text-[0.6875rem] font-extrabold no-underline ${
            active ? "text-bubbles-pink-ink" : "text-muted"
          }`}
        >
          <NavIcon id={item.id} size={22} />
          {item.label}
        </Link>
      </li>
    );
  };
  const talk = MOBILE_TABS[2];
  return (
    <>
      <nav
        className="lg:hidden sticky bottom-0 z-sticky px-3 pb-[max(12px,env(safe-area-inset-bottom))] pt-2 bg-gradient-to-t from-blush via-blush/95 to-transparent"
        aria-label="Bubbles navigation"
      >
        <ul className="m-0 flex list-none items-end justify-around gap-1 rounded-[26px] border-2 border-line bg-surface px-2 py-1.5 shadow-lg">
          {tabLink(MOBILE_TABS[0])}
          {tabLink(MOBILE_TABS[1])}
          <li>
            <Link
              href={talk.href}
              aria-label="Talk to Bubbles"
              aria-current={isActive(pathname, talk.href) ? "page" : undefined}
              className="bubbles-press -mt-7 flex h-[60px] w-[60px] items-center justify-center rounded-full bg-bubbles-pink-ink text-white no-underline shadow-[0_5px_0_var(--bubbles-pink-deep)]"
            >
              <NavIcon id="companion" size={26} />
            </Link>
          </li>
          {tabLink(MOBILE_TABS[3])}
          <li>
            <button
              type="button"
              aria-haspopup="dialog"
              aria-expanded={moreOpen}
              onClick={() => setMoreOpen(true)}
              className={`flex min-h-[48px] min-w-[56px] flex-col items-center justify-center gap-0.5 rounded-2xl text-[0.6875rem] font-extrabold ${
                !onTab ? "text-bubbles-pink-ink" : "text-muted"
              }`}
            >
              <NavIcon id="more" size={22} />
              More
            </button>
          </li>
        </ul>
      </nav>
      <MoreSheet open={moreOpen} onClose={closeMore} />
    </>
  );
}


export function Header({
  apiStatus,
  currentPage,
}: {
  apiStatus: "checking" | "online" | "offline";
  currentPage?: string;
}) {
  return (
    <>
      <header className="sticky top-0 z-sticky w-full border-b border-soft bg-blush/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-content items-center justify-between gap-4 px-gutter py-3">
          <div className="flex min-w-0 items-center gap-3">
            <Link href="/dashboard" className="lg:hidden flex items-center gap-2 no-underline text-default" aria-label="Bubbles home">
              <BubblesMascot size={36} animated={false} />
            </Link>
            {currentPage && (
              <p className="m-0 truncate font-display text-h3 text-default">{currentPage}</p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <span className="hidden sm:inline-flex"><StatusLine apiStatus={apiStatus} /></span>
            <NotificationBell />
            <Link
              href="/profile"
              className="bubbles-press flex h-11 w-11 items-center justify-center rounded-full border-2 border-line bg-surface text-muted no-underline hover:text-default"
              aria-label="Your profile"
            >
              <NavIcon id="profile" size={20} />
            </Link>
          </div>
        </div>
      </header>

      {/* Ask Bubbles: floating button + quick-ask dialog, available on every app page */}
      <AskBubbles />
    </>
  );
}

const BANNER_SHELL = "mx-auto mt-4 w-[calc(100%-2rem)] max-w-content rounded-3xl border-2 border-line px-5 py-4 bubbles-rise";
const BANNER_BUTTON =
  "bubbles-press inline-flex min-h-[44px] items-center justify-center rounded-full px-5 text-body-sm font-extrabold disabled:opacity-60";
const DISMISS_KEY = "bubbles.connection-notice.dismissed";

// sessionStorage can throw (private windows, blocked storage); a banner that cannot remember is still fine.
function readDismissed(kind: string): boolean {
  try {
    return typeof window !== "undefined" && window.sessionStorage.getItem(DISMISS_KEY) === kind;
  } catch {
    return false;
  }
}

function writeDismissed(kind: string) {
  try {
    window.sessionStorage.setItem(DISMISS_KEY, kind);
  } catch {
    // not remembered; the notice returns on the next page
  }
}

/** Ticks once a second while `active`, so the countdown reads true without re-rendering the whole app. */
function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);
  return now;
}

function OfflineBanner({ title, message, onRetry }: { title: string; message: string; onRetry: () => void | Promise<void> }) {
  const { nextRetryAt, retrying } = useApi();
  const [manual, setManual] = useState(false);
  const now = useNow(nextRetryAt !== null && !retrying);
  const busy = manual || retrying;

  return (
    <div className={`${BANNER_SHELL} bg-tint-pink`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Only the static text is the alert; the ticking countdown stays outside it so it is not re-announced. */}
        <div role="alert" className="flex min-w-0 flex-1 items-center gap-3">
          <BubblesMascot size={40} mood="resting" animated={false} />
          <div className="min-w-0">
            <strong className="block text-body font-extrabold text-bubbles-pink-deep">{title}</strong>
            <span className="block text-body-sm text-muted">{message}</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-2 text-body-sm font-bold text-muted" aria-hidden="true">
            <span className={`h-2 w-2 rounded-full bg-bubbles-sun ${busy ? "motion-safe:animate-pulse" : ""}`} />
            {reconnectStatus(nextRetryAt, now, busy)}
          </span>
          <button
            type="button"
            disabled={busy}
            onClick={async () => {
              setManual(true);
              try {
                await onRetry();
              } finally {
                setManual(false);
              }
            }}
            className={`${BANNER_BUTTON} bg-bubbles-pink-ink text-white shadow-[0_4px_0_var(--bubbles-pink-deep)]`}
          >
            Try again now
          </button>
        </div>
      </div>
    </div>
  );
}

function NoticeBanner({ kind, title, message }: { kind: string; title: string; message: string }) {
  const pathname = usePathname() ?? "";
  const [dismissed, setDismissed] = useState(() => readDismissed(kind));
  if (dismissed) return null;

  return (
    <div role="status" className={`${BANNER_SHELL} flex flex-wrap items-center justify-between gap-3 bg-tint-sky`}>
      <div className="min-w-0 flex-1">
        <strong className="block text-body font-extrabold text-bubbles-sky-deep">{title}</strong>
        <span className="block text-body-sm text-muted">{message}</span>
      </div>
      <div className="flex items-center gap-2">
        {!pathname.startsWith("/settings") && (
          <Link href="/settings" className={`${BANNER_BUTTON} border-2 border-ink bg-surface text-ink no-underline`}>
            Open Settings
          </Link>
        )}
        <button
          type="button"
          onClick={() => {
            writeDismissed(kind);
            setDismissed(true);
          }}
          className={`${BANNER_BUTTON} text-muted hover:text-default`}
        >
          Dismiss
          <span className="sr-only"> this notice</span>
        </button>
      </div>
    </div>
  );
}

/**
 * Global connection notice. Reads the live state from the API context; the props are kept so existing pages that
 * pass them keep working. Offline is a blocking banner that reconnects by itself; compatibility mode (the app
 * works, the database needs a one-time permission update) is a calm, dismissible note; healthy shows nothing.
 */
export function ApiAlert({ connectionError, onRetry }: { connectionError?: string | null; onRetry?: () => void | Promise<void> }) {
  const api = useApi();
  const banner = connectionBanner({
    apiStatus: api.apiStatus,
    connectionError: connectionError ?? api.connectionError,
    health: api.health,
  });
  if (!banner) return null;
  if (banner.kind === "offline") {
    return <OfflineBanner title={banner.title} message={banner.message} onRetry={onRetry ?? api.checkApiHealth} />;
  }
  return <NoticeBanner key={banner.kind} kind={banner.kind} title={banner.title} message={banner.message} />;
}
