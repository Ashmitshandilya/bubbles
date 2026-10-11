"use client";

import dynamic from "next/dynamic";
import { Component, useEffect, useState, type ReactNode } from "react";
import { readStoredTier, worldAllowed } from "../perf/tier";
import { onStoryFrame, story } from "../story/store";

const WorldCanvas = dynamic(() => import("./WorldCanvas"), { ssr: false, loading: () => null });

/** WebGL can fail on any device; the story still works without it. */
class WorldBoundary extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onError();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/**
 * Mounts the 3D world only when it can run (perf/tier.ts `worldAllowed`: motion allowed, WebGL2, no Save-Data, enough
 * memory, no remembered drop to static). Otherwise, or as soon as its WebGL context is lost, the page marks itself
 * `data-world="off"` and the CSS shows the illustrated Bubbles instead. (Slow frames only slow the world down: world/Governor.tsx.)
 */
export function WorldMount() {
  const [source, setSource] = useState<HTMLElement | null>(null);

  useEffect(() => {
    const root = document.querySelector<HTMLElement>(".cw");
    if (!root) return;
    let webgl = false;
    try {
      const probe = document.createElement("canvas").getContext("webgl2");
      webgl = Boolean(probe);
      // Give the probe's context slot back right away (browsers cap live contexts; the real canvas needs one).
      probe?.getExtension("WEBGL_lose_context")?.loseContext();
    } catch {
      webgl = false;
    }
    const nav = navigator as Navigator & { deviceMemory?: number; connection?: { saveData?: boolean } };
    const allowed = worldAllowed({
      reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      webgl2: webgl,
      saveData: nav.connection?.saveData === true,
      deviceMemory: nav.deviceMemory,
      storedTier: readStoredTier(window.sessionStorage),
    });
    if (!allowed) {
      root.dataset.world = "off";
      return;
    }
    root.dataset.world = "loading";
    setSource(root);
  }, []);

  // A lost context unmounts the world for the rest of the visit (its unmount marks the page "off").
  useEffect(() => {
    if (!source) return;
    return onStoryFrame(() => {
      if (story.worldLost) {
        source.dataset.world = "off";
        setSource(null);
      }
    });
  }, [source]);

  if (!source) return null;
  return (
    <div className="cw-world" aria-hidden="true">
      <WorldBoundary
        onError={() => {
          source.dataset.world = "off";
        }}
      >
        <WorldCanvas eventSource={source} />
      </WorldBoundary>
    </div>
  );
}
