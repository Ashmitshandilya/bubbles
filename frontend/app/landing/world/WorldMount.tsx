"use client";

import dynamic from "next/dynamic";
import { Component, useEffect, useState, type ReactNode } from "react";

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
 * Mounts the 3D world only when it can run well: motion allowed and WebGL2
 * available. Otherwise the page marks itself `data-world="off"` and the CSS shows
 * the illustrated Bubbles instead.
 */
export function WorldMount() {
  const [source, setSource] = useState<HTMLElement | null>(null);

  useEffect(() => {
    const root = document.querySelector<HTMLElement>(".cw");
    if (!root) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let webgl = false;
    try {
      const probe = document.createElement("canvas").getContext("webgl2");
      webgl = Boolean(probe);
      // Give the probe's context slot back right away (browsers cap live contexts; the real canvas needs one).
      probe?.getExtension("WEBGL_lose_context")?.loseContext();
    } catch {
      webgl = false;
    }
    if (reduced || !webgl) {
      root.dataset.world = "off";
      return;
    }
    root.dataset.world = "loading";
    setSource(root);
  }, []);

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
