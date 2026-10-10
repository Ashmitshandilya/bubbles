"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { canPromote, pickInitialTier, readStoredTier } from "../perf/tier";
import { story } from "../story/store";

const SkyCanvas = dynamic(() => import("./SkyCanvas"), { ssr: false, loading: () => null });

type Hints = Navigator & { deviceMemory?: number; connection?: { saveData?: boolean } };

/**
 * Chooses the starting tier (perf/tier.ts) and, unless it is static, loads the sky shader.
 * Static (reduced motion, no WebGL2, Save-Data, a remembered demotion) mounts nothing: the CSS
 * gradient in `.cw-bg` is the sky. It lives inside `.cw-bg` so the chapter scrim and vignette
 * layer over the canvas.
 */
export function SkyMount() {
  const [live, setLive] = useState<null | { mobile: boolean; promotable: boolean }>(null);

  useEffect(() => {
    const nav = navigator as Hints;
    const mobile = window.innerWidth < 820 || window.matchMedia("(pointer: coarse)").matches;
    const stored = readStoredTier(window.sessionStorage);
    const tier = pickInitialTier({
      reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      // A capability check only; the sky creates (and may lose) the real context itself.
      webgl2: typeof WebGL2RenderingContext !== "undefined",
      saveData: nav.connection?.saveData === true,
      mobile,
      deviceMemory: nav.deviceMemory,
      hardwareConcurrency: nav.hardwareConcurrency,
      pausedByUser: story.paused,
      storedTier: stored,
    });
    story.tier = tier;
    if (tier === "static") return;
    // A remembered demotion also means "do not try full again this visit".
    setLive({ mobile, promotable: stored === null && canPromote({ mobile, deviceMemory: nav.deviceMemory, hardwareConcurrency: nav.hardwareConcurrency }) });
  }, []);

  return live ? <SkyCanvas mobile={live.mobile} promotable={live.promotable} /> : null;
}
