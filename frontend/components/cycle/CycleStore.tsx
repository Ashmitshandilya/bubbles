"use client";

// Shared cycle state shape + hooks. Kept apart from the provider so the Log sheet (which the provider renders) can
// read the context without a circular import.

import { createContext, useContext, useEffect, useRef } from "react";
import type { ChipGroup, CycleSettings, DayResponse, Overview } from "../../app/lib/cycle-types";

export type CallResult<T> = { ok: true; data: T } | { ok: false; error: string };
type Status = "loading" | "error" | "ready";

export interface CycleCtx {
  /** The viewer's local calendar day (the server would otherwise use the UTC date). */
  today: string;
  overview: Overview | null;
  overviewStatus: Status;
  overviewError: string;
  reloadOverview: () => void;
  settings: CycleSettings | null;
  settingsStatus: Status;
  settingsError: string;
  tempUnit: "c" | "f";
  reloadSettings: () => void;
  saveSettings: (partial: Record<string, unknown>) => Promise<string | null>;
  factors: ChipGroup[] | null;
  factorsStatus: Status;
  reloadFactors: () => void;
  /** Bumps after any change so open tabs can refetch their own data. */
  rev: number;
  applyOverview: (overview: Overview | null) => void;
  bump: () => void;
  openLog: (date?: string) => void;
  announce: (message: string) => void;
  call: <T,>(path: string, init?: RequestInit) => Promise<CallResult<T>>;
  postPeriod: (kind: "start" | "end", date: string | null) => Promise<CallResult<DayResponse>>;
  reloadAll: () => void;
}

export const Ctx = createContext<CycleCtx | null>(null);

export function useCycle(): CycleCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCycle must be used inside CycleProvider");
  return ctx;
}

/** Runs `reload` whenever the shared revision changes (not on first render). */
export function useReloadOnRev(reload: () => void, rev: number) {
  const seen = useRef(rev);
  useEffect(() => {
    if (seen.current === rev) return;
    seen.current = rev;
    reload();
  }, [rev, reload]);
}

