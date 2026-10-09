"use client";

// Data plumbing for the Whole-Health OS pages. Everything goes through useApi().fetchBubbles (timeouts, https guard,
// reconnect handling) or useBubblesQuery; nothing here calls fetch directly.

import { useMemo, useSyncExternalStore } from "react";
import { useBubblesQuery, type Query } from "../hub/HubKit";
import { tzOffsetMinutes, withQuery } from "../../app/lib/wellness-format";

export { useWellnessSend, type SendResult } from "./send";

/** GET with the local-day parameter attached. `path` may already carry a query string. */
export function useWellnessQuery<T>(path: string, options: { tz?: boolean } = {}): [Query<T>, () => void] {
  const tz = options.tz !== false;
  const full = useMemo(() => (tz ? withQuery(path, { tz_offset_minutes: tzOffsetMinutes() }) : path), [path, tz]);
  return useBubblesQuery<T>(full);
}

const REDUCED = "(prefers-reduced-motion: reduce)";

function subscribeMotion(onChange: () => void) {
  const media = window.matchMedia(REDUCED);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

/** True when the device asks for less motion. Animations must then be off and timing shown as text. */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribeMotion, () => window.matchMedia(REDUCED).matches, () => true);
}
