import type { CSSProperties } from "react";
import { burstDroplets } from "../app/lib/soap-pop";

const DROPLETS = burstDroplets();

/**
 * A tiny soap-bubble burst for "saved" moments. Put it inside a `relative` box; it centres on that box, draws
 * nothing until it mounts (mount it when the save happens) and is hidden entirely under prefers-reduced-motion
 * (see .soap-pop in globals.css). Purely decorative: the message next to it carries the meaning.
 */
export function SoapPop() {
  return (
    <span aria-hidden="true" className="soap-pop">
      <span className="soap-pop-ring" />
      {DROPLETS.map((d, i) => (
        <span
          key={i}
          className="soap-pop-drop"
          style={{ "--dx": `${d.x}px`, "--dy": `${d.y}px`, "--size": `${d.size}px`, animationDelay: `${d.delay}ms` } as CSSProperties}
        />
      ))}
    </span>
  );
}
