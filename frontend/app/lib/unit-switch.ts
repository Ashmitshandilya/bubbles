// Pure helpers for showing and entering a body measurement in lbs or kg. The API always stores lbs for these trackers.
// No React. Tested in unit-switch.test.ts.

import { LB_PER_KG } from "./fitness-calc";

export type SwitchUnit = "lbs" | "kg";

const round1 = (n: number) => Math.round(n * 10) / 10;

/** Stored value (lbs) -> the unit on screen. */
export function toShownUnit(lbs: number, unit: SwitchUnit): number {
  return unit === "kg" ? round1(lbs / LB_PER_KG) : lbs;
}

/** Value typed on screen -> lbs for the API. */
export function toStoredUnit(value: number, unit: SwitchUnit): number {
  return unit === "kg" ? round1(value * LB_PER_KG) : value;
}

const KEY_PREFIX = "bubbles.unit.";

/** Per-viewer convenience only: the last unit chosen on this device. Falls back to lbs when storage is unavailable. */
export function readUnitPreference(scope: string): SwitchUnit {
  try {
    return window.localStorage.getItem(KEY_PREFIX + scope) === "kg" ? "kg" : "lbs";
  } catch {
    return "lbs";
  }
}

export function saveUnitPreference(scope: string, unit: SwitchUnit): void {
  try {
    window.localStorage.setItem(KEY_PREFIX + scope, unit);
  } catch {
    // Private window or blocked storage: the choice lasts for this visit only.
  }
}
