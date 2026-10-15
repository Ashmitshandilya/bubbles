"use client";

// Privacy veil. While it is switched on in Settings, anything marked `data-private` is blurred whenever the tab is
// hidden, the window loses focus, or the person presses Hide. A tap on a blurred value shows everything again.
// The blur itself is one CSS rule keyed on <html data-privacy-veil="on"> (globals.css), so no page re-renders.

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { isVeiled, nextCover, readVeilSetting, writeVeilSetting, type CoverEvent, type VeilStore } from "../app/lib/privacy-veil";

interface VeilValue {
  /** The Settings choice. Default off. */
  enabled: boolean;
  /** Values are currently hidden (only ever true while `enabled`). */
  covered: boolean;
  setEnabled: (on: boolean) => void;
  toggleCover: () => void;
}

const VeilContext = createContext<VeilValue>({ enabled: false, covered: false, setEnabled: () => {}, toggleCover: () => {} });

export const useVeil = () => useContext(VeilContext);

function localStore(): VeilStore | null {
  try {
    return window.localStorage;
  } catch {
    return null; // blocked site data: the choice lasts until the page closes
  }
}

export function PrivacyVeilProvider({ children }: { children: ReactNode }) {
  // Starts off on the server and on first paint; the saved choice is read after mount so hydration always matches.
  const [enabled, setEnabledState] = useState(false);
  const [covered, setCovered] = useState(false);
  const veiled = isVeiled(enabled, covered);

  useEffect(() => {
    setEnabledState(readVeilSetting(localStore()));
  }, []);

  const setEnabled = useCallback((on: boolean) => {
    setEnabledState(on);
    if (!on) setCovered(false);
    writeVeilSetting(localStore(), on);
  }, []);

  const cover = useCallback((event: CoverEvent) => setCovered((current) => nextCover(current, event)), []);
  const toggleCover = useCallback(() => cover("toggle"), [cover]);

  // Watching the tab costs nothing while the setting is off.
  useEffect(() => {
    if (!enabled) return;
    const away = () => cover("away");
    const onVisibility = () => {
      if (document.hidden) away();
    };
    onVisibility();
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", away);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", away);
    };
  }, [enabled, cover]);

  // While veiled: flag <html> for the CSS, and let the first tap on a blurred value reveal instead of acting
  // (a blurred tile is also a link, so the tap is swallowed rather than navigating blind).
  useEffect(() => {
    if (!veiled) return;
    const root = document.documentElement;
    root.setAttribute("data-privacy-veil", "on");
    const reveal = (event: MouseEvent) => {
      if (!(event.target instanceof Element) || !event.target.closest("[data-private]")) return;
      event.preventDefault();
      event.stopPropagation();
      cover("reveal");
    };
    document.addEventListener("click", reveal, true);
    return () => {
      document.removeEventListener("click", reveal, true);
      root.removeAttribute("data-privacy-veil");
    };
  }, [veiled, cover]);

  const value = useMemo(() => ({ enabled, covered: veiled, setEnabled, toggleCover }), [enabled, veiled, setEnabled, toggleCover]);

  return (
    <VeilContext.Provider value={value}>
      {children}
      <p role="status" className="sr-only">{veiled ? "Private details are hidden. Tap a blurred area to show them." : ""}</p>
    </VeilContext.Provider>
  );
}

function Eye({ off }: { off: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className="shrink-0">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
      {off && <path d="M4 4l16 16" />}
    </svg>
  );
}

/** The Hide button. Renders nothing unless the veil is switched on in Settings. Drop it anywhere, for example in the app header. */
export function VeilToggle({ className = "" }: { className?: string }) {
  const { enabled, covered, toggleCover } = useVeil();
  if (!enabled) return null;
  return (
    <button
      type="button"
      aria-pressed={covered}
      aria-label="Hide private details"
      onClick={toggleCover}
      className={`bubbles-press inline-flex min-h-[44px] items-center gap-2 rounded-full border-2 px-4 text-sm font-extrabold ${
        covered ? "border-bubbles-grape bg-bubbles-grape text-white" : "border-line-grape bg-surface text-bubbles-grape-deep"
      } ${className}`}
    >
      <Eye off={covered} />
      Hide
    </button>
  );
}

/** The Settings switch. `labelledBy` points at the visible row label. */
export function VeilSwitch({ labelledBy, describedBy }: { labelledBy: string; describedBy?: string }) {
  const { enabled, setEnabled } = useVeil();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      onClick={() => setEnabled(!enabled)}
      className="bubbles-press inline-flex min-h-[44px] items-center gap-3 rounded-full px-1"
    >
      <span className="text-body-sm font-bold text-muted">{enabled ? "On" : "Off"}</span>
      <span aria-hidden="true" className={`relative block h-7 w-12 rounded-full border-2 transition-colors ${enabled ? "border-bubbles-grape bg-bubbles-grape" : "border-ink-faint bg-surface"}`}>
        <span className={`absolute left-0 top-1 block h-4 w-4 rounded-full transition-transform motion-reduce:transition-none ${enabled ? "translate-x-6 bg-white" : "translate-x-1 bg-ink-faint"}`} />
      </span>
    </button>
  );
}
