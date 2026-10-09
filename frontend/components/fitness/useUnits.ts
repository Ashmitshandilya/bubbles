"use client";

import { useBubblesQuery } from "../hub/HubKit";
import type { Units } from "../../app/lib/fitness-calc";
import type { BodyResponse } from "../../app/lib/fitness-types";

/** The unit system chosen in Fitness setup. Metric until the profile says otherwise (or fails to load). */
export function useUnits(): Units {
  const [q] = useBubblesQuery<BodyResponse>("/profile/body");
  return q.status === "ready" && q.data.profile.units === "imperial" ? "imperial" : "metric";
}
