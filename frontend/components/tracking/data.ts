"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useApi, useAuth } from "../Providers";
import { responseFailure } from "../../lib/api";
import { classifyFailure, failureFromError, saveFailureMessage } from "../../app/lib/connection";
import { calendarDay, parseWhen } from "../../app/lib/dates";
import { adaptTrackerEntry, readEntries } from "../../app/lib/api-adapters";

export type EntryValue = string | number | boolean | null | undefined;

/** One row from GET /health/<slug>: `{id, date, ...fields}` (see backend/health_logs.py). */
export interface Entry {
  id: string;
  date: string;
  [key: string]: EntryValue;
}

/* ── Dates ───────────────────────────────────────────────────────────── */

const DAY_MS = 86_400_000;

/**
 * Calendar days ("2026-10-05", and the UTC-midnight stamp the API returns for a day-only pick) parse as LOCAL
 * midnight, not UTC. See app/lib/dates.ts.
 */
export { parseWhen };

export function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

/** Whole calendar days between `value` and today (0 = today, 1 = yesterday, negative = future). */
export function daysAgo(value: string, now = new Date()): number {
  return Math.round((startOfDay(now).getTime() - startOfDay(parseWhen(value)).getTime()) / DAY_MS);
}

export function dayLabel(value: string, now = new Date()): string {
  const d = parseWhen(value);
  if (Number.isNaN(d.getTime())) return "Undated";
  const ago = daysAgo(value, now);
  if (ago === 0) return "Today";
  if (ago === 1) return "Yesterday";
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    ...(d.getFullYear() !== now.getFullYear() ? { year: "numeric" } : {}),
  });
}

export function dateLabel(value: string): string {
  const d = parseWhen(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/** Clock time for timestamped entries; "" for date-only entries (a day-only pick has no time of day). */
export function timeLabel(value: string): string {
  if (value.length <= 10 || calendarDay(value)) return "";
  const d = parseWhen(value);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/** Today as a local YYYY-MM-DD (for <input type="date">). */
export function todayISO(now = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function byNewest(a: Entry, b: Entry): number {
  return parseWhen(b.date).getTime() - parseWhen(a.date).getTime();
}

/* ── Values ──────────────────────────────────────────────────────────── */

export function present(v: EntryValue): boolean {
  return v !== undefined && v !== null && v !== "";
}

export function toNumber(v: EntryValue): number | null {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/** "250 ml", "7.5 h", "8/10", "98.6°F". */
export function formatNumber(n: number, unit = "", decimals = 1): string {
  const text = n.toLocaleString(undefined, { maximumFractionDigits: decimals });
  if (!unit) return text;
  return /^[/°%]/.test(unit) ? `${text}${unit}` : `${text} ${unit}`;
}

/** Same "lo-hi" grammar the backend accepts for lab reference ranges. */
export function parseRange(v: EntryValue): [number, number] | null {
  const m = /^\s*(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)\s*$/.exec(String(v ?? ""));
  return m ? [Number(m[1]), Number(m[2])] : null;
}

/* ── Stats ───────────────────────────────────────────────────────────── */

/**
 * Serializable summary-stat recipe (server pages pass these to the client tracker).
 * `days` = calendar days including today (1 = today only, 7 = this past week).
 */
export interface StatSpec {
  label: string;
  kind: "count" | "countWhere" | "distinct" | "latest" | "avg" | "sum" | "dailyAvg" | "outOfRange";
  field?: string;
  /** countWhere: case-insensitive match value. */
  equals?: string;
  /** outOfRange: entry field holding a "lo-hi" range. */
  rangeField?: string;
  days?: number;
  unit?: string;
  decimals?: number;
  /** Sub-line under the value; `latest` defaults to the entry's day. */
  note?: string;
}

/** `value: null` means there is no data to compute it from — shown as a gap, never as zero. */
export interface StatValue {
  label: string;
  value: string | null;
  note?: string;
  /** Text shown instead of a value when `value` is null (default "Not logged yet"). */
  gap?: string;
}

export function computeStat(spec: StatSpec, entries: Entry[], now = new Date()): StatValue {
  const days = spec.days;
  const scoped = days
    ? entries.filter((e) => {
        const ago = daysAgo(e.date, now);
        return ago >= 0 && ago < days;
      })
    : entries;
  const field = spec.field ?? "";
  const numbers = scoped.map((e) => toNumber(e[field])).filter((n): n is number => n !== null);
  const total = numbers.reduce((a, b) => a + b, 0);
  const fmt = (n: number) => formatNumber(n, spec.unit, spec.decimals ?? 1);
  let value: string | null = null;
  let note = spec.note;

  switch (spec.kind) {
    case "count":
      value = String(scoped.length);
      break;
    case "countWhere": {
      const want = (spec.equals ?? "").toLowerCase();
      value = String(scoped.filter((e) => String(e[field] ?? "").toLowerCase() === want).length);
      break;
    }
    case "distinct":
      value = String(new Set(scoped.map((e) => String(e[field] ?? "").trim().toLowerCase()).filter(Boolean)).size);
      break;
    case "sum":
      value = numbers.length ? fmt(total) : null;
      break;
    case "avg":
      value = numbers.length ? fmt(total / numbers.length) : null;
      break;
    case "dailyAvg": {
      const loggedDays = new Set(
        scoped.filter((e) => toNumber(e[field]) !== null).map((e) => startOfDay(parseWhen(e.date)).getTime()),
      ).size;
      value = loggedDays ? fmt(total / loggedDays) : null;
      break;
    }
    case "latest": {
      const hit = [...scoped].sort(byNewest).find((e) => present(e[field]));
      if (hit) {
        const n = toNumber(hit[field]);
        value = n !== null ? fmt(n) : String(hit[field]);
        note = note ?? dayLabel(hit.date, now);
      }
      break;
    }
    case "outOfRange": {
      const ranged = scoped.filter((e) => toNumber(e[field]) !== null && parseRange(e[spec.rangeField ?? ""]));
      value = ranged.length
        ? String(
            ranged.filter((e) => {
              const n = toNumber(e[field]) as number;
              const [lo, hi] = parseRange(e[spec.rangeField ?? ""]) as [number, number];
              return n < lo || n > hi;
            }).length,
          )
        : null;
      break;
    }
  }
  return { label: spec.label, value, note };
}

/* ── Data hook ───────────────────────────────────────────────────────── */

export type LoadStatus = "loading" | "ready" | "error";

/**
 * Loads `GET <endpoint>?days=N` and saves via `POST <endpoint>`.
 * `save` resolves null on success (the saved entry is added to the list) or an error message.
 * `refetchAfterSave` reloads after saving (for endpoints whose `summary` depends on all entries).
 */
export function useTracker(endpoint: string, days: number, refetchAfterSave = false) {
  const { session } = useAuth();
  const { fetchBubbles, reconnects } = useApi();
  const token = session?.access_token;
  const slug = endpoint.replace(/^\/health\//, "");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [summary, setSummary] = useState<unknown>(null);
  const [status, setStatus] = useState<LoadStatus>("loading");
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [freshId, setFreshId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let alive = true;
    (async () => {
      try {
        const response = await fetchBubbles(`${endpoint}?days=${days}`);
        if (!alive) return;
        if (!response.ok) {
          setError((await responseFailure(response)).message);
          setStatus("error");
          return;
        }
        const payload: { entries?: unknown; summary?: unknown } = await response.json();
        if (!alive) return;
        setEntries(readEntries<Entry>(payload?.entries).map((e) => adaptTrackerEntry(slug, e)));
        setSummary(payload?.summary ?? null);
        setStatus("ready");
      } catch (error) {
        if (!alive) return;
        setError(classifyFailure(failureFromError(error)).message);
        setStatus("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [token, endpoint, slug, days, reloadKey, fetchBubbles]);

  const retry = useCallback(() => {
    setStatus("loading");
    setReloadKey((k) => k + 1);
  }, []);

  // Bubbles came back after being offline: reload a failed list by itself.
  const seenReconnects = useRef(reconnects);
  useEffect(() => {
    if (seenReconnects.current === reconnects) return;
    seenReconnects.current = reconnects;
    if (status === "error") retry();
  }, [reconnects, status, retry]);

  const save = useCallback(
    async (body: Record<string, string | number>): Promise<string | null> => {
      try {
        const response = await fetchBubbles(endpoint, {
          method: "POST",
          body: JSON.stringify({ date: new Date().toISOString(), ...body }),
        });
        if (!response.ok) return saveFailureMessage(await responseFailure(response));
        const payload: { entry?: Entry; status?: string; message?: string } | null = await response.json().catch(() => null);
        // The safety engine answered instead of saving (crisis or urgent wording in a note): show its words, nothing was stored.
        if (payload?.status === "safety" && payload.message) return payload.message;
        // A saved entry without an id cannot be listed; the reload below picks it up instead.
        const entry = payload?.entry?.id ? adaptTrackerEntry(slug, readEntries<Entry>([payload.entry])[0]) : undefined;
        if (entry?.id) {
          setEntries((list) => [entry, ...list.filter((e) => e.id !== entry.id)]);
          setFreshId(entry.id);
        }
        if (refetchAfterSave || !entry?.id) setReloadKey((k) => k + 1);
        return null;
      } catch (error) {
        return saveFailureMessage(classifyFailure(failureFromError(error)));
      }
    },
    [fetchBubbles, endpoint, slug, refetchAfterSave],
  );

  return { entries, summary, status, error, retry, save, freshId };
}
