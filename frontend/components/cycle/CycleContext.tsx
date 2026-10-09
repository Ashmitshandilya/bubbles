"use client";

// One provider for the whole cycle section: the overview (kept fresh after every save), settings, the chip catalogue,
// a tiny API wrapper and the "Log" sheet that every tab can open.

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useApi } from "../Providers";
import { useBubblesQuery } from "../hub/HubKit";
import { classifyFailure, failureFromError } from "../../app/lib/connection";
import { responseError } from "../../lib/api";
import { periodBody, withToday } from "../../app/lib/cycle-api";
import { todayISO } from "../../app/lib/cycle-calendar";
import type { DayResponse, FactorsResponse, Overview, CycleSettings, SettingsResponse } from "../../app/lib/cycle-types";
import { LogSheet } from "./LogSheet";
import { Ctx, type CallResult, type CycleCtx } from "./CycleStore";

export function CycleProvider({ children }: { children: ReactNode }) {
  const { fetchBubbles } = useApi();
  const [today] = useState(() => todayISO());
  const [overviewQuery, reloadOverview] = useBubblesQuery<Overview>(withToday("/cycle/overview", today));
  const [settingsQuery, reloadSettings] = useBubblesQuery<SettingsResponse>("/cycle/settings");
  const [factorsQuery, reloadFactors] = useBubblesQuery<FactorsResponse>("/cycle/factors");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [settings, setSettings] = useState<CycleSettings | null>(null);
  const [rev, setRev] = useState(0);
  const [message, setMessage] = useState("");
  const [sheet, setSheet] = useState<{ open: boolean; date: string }>({ open: false, date: today });
  const opener = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (overviewQuery.status === "ready") setOverview(overviewQuery.data);
  }, [overviewQuery]);
  useEffect(() => {
    if (settingsQuery.status === "ready") setSettings(settingsQuery.data.settings);
  }, [settingsQuery]);

  const bump = useCallback(() => setRev((n) => n + 1), []);
  const announce = useCallback((m: string) => setMessage(m), []);

  const call = useCallback(
    async <T,>(path: string, init: RequestInit = {}): Promise<CallResult<T>> => {
      try {
        const response = await fetchBubbles(path, init);
        if (!response.ok) return { ok: false, error: await responseError(response) };
        return { ok: true, data: (await response.json()) as T };
      } catch (error) {
        return { ok: false, error: classifyFailure(failureFromError(error)).message };
      }
    },
    [fetchBubbles],
  );

  const saveSettings = useCallback(
    async (partial: Record<string, unknown>) => {
      const result = await call<SettingsResponse>(withToday("/cycle/settings", today), { method: "PUT", body: JSON.stringify(partial) });
      if (!result.ok) return result.error;
      setSettings(result.data.settings);
      if (result.data.overview) setOverview(result.data.overview);
      else reloadOverview();
      bump();
      return null;
    },
    [call, today, reloadOverview, bump],
  );

  const postPeriod = useCallback(
    async (kind: "start" | "end", date: string | null) => {
      const result = await call<DayResponse>(`/cycle/period/${kind}`, { method: "POST", body: JSON.stringify(periodBody(date, today)) });
      if (result.ok) {
        if (result.data.overview) setOverview(result.data.overview);
        else reloadOverview();
        bump();
      }
      return result;
    },
    [call, today, reloadOverview, bump],
  );

  const openLog = useCallback(
    (date?: string) => {
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      setSheet({ open: true, date: date ?? today });
    },
    [today],
  );

  const closeLog = useCallback(() => {
    setSheet((s) => ({ ...s, open: false }));
    window.setTimeout(() => opener.current?.focus(), 0);
  }, []);

  const reloadAll = useCallback(() => {
    reloadOverview();
    reloadSettings();
    bump();
  }, [reloadOverview, reloadSettings, bump]);

  const value = useMemo<CycleCtx>(
    () => ({
      today,
      overview,
      overviewStatus: overview ? "ready" : overviewQuery.status === "error" ? "error" : "loading",
      overviewError: overviewQuery.status === "error" ? overviewQuery.message : "",
      reloadOverview,
      settings,
      settingsStatus: settings ? "ready" : settingsQuery.status === "error" ? "error" : "loading",
      settingsError: settingsQuery.status === "error" ? settingsQuery.message : "",
      tempUnit: settings?.temp_unit ?? "c",
      reloadSettings,
      saveSettings,
      factors: factorsQuery.status === "ready" ? factorsQuery.data.groups : null,
      factorsStatus: factorsQuery.status,
      reloadFactors,
      rev,
      applyOverview: setOverview,
      bump,
      openLog,
      announce,
      call,
      postPeriod,
      reloadAll,
    }),
    [today, overview, overviewQuery, settings, settingsQuery, reloadOverview, reloadSettings, saveSettings, factorsQuery, reloadFactors, rev, bump, openLog, announce, call, postPeriod, reloadAll],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      <div role="status" aria-live="polite" className="sr-only">{message}</div>
      <LogSheet open={sheet.open} date={sheet.date} onDateChange={(date) => setSheet({ open: true, date })} onClose={closeLog} />
    </Ctx.Provider>
  );
}
