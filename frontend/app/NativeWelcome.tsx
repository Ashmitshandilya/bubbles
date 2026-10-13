import type { CSSProperties } from "react";
import Link from "next/link";
import { display } from "./landing/Landing";
import { BubblesLogo } from "./landing/BubblesMark";
import { BubblesFigure } from "./landing/BubblesFigure";
import { SoapCss } from "./landing/bubbles/SoapCss";
import { COLOR_SCRIPT } from "./landing/atmosphere/palette";
import { calmBackground } from "./landing/atmosphere/sky";
import "./landing/landing.css";

/*
 * The Android app's first screen for signed-out people (NativeEntry shows it at "/"): the website landing's opening
 * scene at its static tier. Same dawn sky, CSS soap bubbles, illustrated Bubbles, type and buttons; no WebGL, so cheap
 * phones stay smooth, and every animation here is already off under reduced motion (landing.css).
 * Rendered on the server and handed to NativeEntry, so none of it ships in a client chunk.
 */

type Vars = CSSProperties & Record<`--${string}`, string>;

const SKY = { "--calm-sky": calmBackground(COLOR_SCRIPT[0], false), "--calm-sky-ok": calmBackground(COLOR_SCRIPT[0], true) } as Vars;

export function NativeWelcome() {
  return (
    <main className={`cw nw ${display.variable}`} data-tone="light" style={SKY}>
      <SoapCss variant="hero" />
      <BubblesLogo size={34} className="nw-logo" />
      <div className="nw-figure">
        <BubblesFigure
          uid="nw"
          pose="wave"
          mood="happy"
          title="Bubbles, a baby unicorn doctor in a nurse cap and a doctor's coat, waving hello"
        />
      </div>
      <div className="nw-copy bubbles-rise">
        <h1 className="cw-display">
          Your body keeps a story. <span className="cw-accent">Bubbles remembers&nbsp;it.</span>
        </h1>
        <p className="cw-lede">A calm health companion that listens, remembers and connects the dots over time.</p>
      </div>
      <div className="nw-actions bubbles-rise">
        <Link href="/login?mode=signup" className="cw-btn cw-btn--primary cw-btn--lg">
          Get started
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </Link>
        <Link href="/login" className="cw-btn cw-btn--ghost cw-btn--lg">
          I already have an account
        </Link>
        <p className="cw-fineprint">Bubbles is a wellness companion and does not diagnose.</p>
      </div>
    </main>
  );
}
