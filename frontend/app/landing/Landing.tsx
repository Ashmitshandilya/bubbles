import type { CSSProperties } from "react";
import Link from "next/link";
import { Bricolage_Grotesque, Geist_Mono } from "next/font/google";
import { AuthCta } from "./AuthCta";
import { BubblesLogo } from "./BubblesMark";
import { BubblesFigure } from "./BubblesFigure";
import { SoapCss } from "./bubbles/SoapCss";
import { ScrollDirector } from "./story/ScrollDirector";
import { ChapterRail } from "./story/ChapterRail";
import { PauseMotion } from "./story/PauseMotion";
import { COLOR_SCRIPT, phaseInk } from "./atmosphere/palette";
import { SkyMount } from "./atmosphere/SkyMount";
import { calmBackground, skyGradient, skyVars } from "./atmosphere/sky";
import { CHAPTERS, MOBILE_LEN_FACTOR } from "./story/store";
import { SpeechBubble } from "./story/SpeechBubble";
import { BubblesHost } from "./story/BubblesHost";
import { TravelRoutes } from "./story/TravelRoutes";
import { SystemLabels } from "./story/SystemLabels";
import { TypedIntake } from "./story/TypedIntake";
import { CycleDay } from "./story/CycleDay";
import { ConnectWeb } from "./story/ConnectWeb";
import { CompanionDemo } from "./story/CompanionDemo";
import { WorldMount } from "./world/WorldMount";
import "./landing.css";

/*
 * The Bubbles landing page: one continuous, scroll-driven story.
 *
 *   enter → body → numbers → track → cycle → connect → memory → companion → care → Bubbles
 *
 * Each chapter is a tall section that only provides scroll length; its layers
 * are fixed to the viewport and choreographed by CSS custom properties written
 * by <ScrollDirector/>. A single WebGL canvas (<WorldMount/>) renders Bubbles and the
 * living spine between the back and front layers. With reduced motion (or no
 * JavaScript) the same content renders as a calm, normally scrolling page.
 */

/** What the illustrated Bubbles looks like, for the calm page (the figure is drawn, so this is its text alternative). */
const BUBBLES_ALT = "Bubbles, a baby unicorn doctor in a nurse cap and a doctor's coat, with a heart stethoscope";

const display = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-cw-display", axes: ["opsz", "wdth"], display: "swap" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-cw-mono", display: "swap" });

type Vars = CSSProperties & Record<`--${string}`, string | number>;

/*
 * The server-rendered sky: the opening (dawn) colours, the mobile chapter-length factor, and the
 * skies the two portals open onto (the body for the dive, the care chapter for the bloom), so a
 * portal's fill matches the sky it reveals.
 */
const CHAPTER_SKY = (key: (typeof CHAPTERS)[number]["key"]) => COLOR_SCRIPT[CHAPTERS.findIndex((c) => c.key === key)].sky;
const ROOT_VARS = {
  ...skyVars(COLOR_SCRIPT[0]),
  "--lenk-m": MOBILE_LEN_FACTOR,
  "--sky-body": skyGradient(CHAPTER_SKY("body"), false),
  "--sky-body-ok": skyGradient(CHAPTER_SKY("body"), true),
  "--sky-care": skyGradient(CHAPTER_SKY("care"), false),
  "--sky-care-ok": skyGradient(CHAPTER_SKY("care"), true),
} as Vars;

const chapter = (key: (typeof CHAPTERS)[number]["key"]) => {
  const index = CHAPTERS.findIndex((c) => c.key === key);
  const c = CHAPTERS[index];
  return {
    id: c.id,
    "data-chapter": c.key,
    "data-tone": c.tone,
    className: `cw-ch cw-ch--${c.key}`,
    // --calm-sky: this chapter's sky as its background on the calm page (OKLab, with a plain sRGB fallback).
    style: {
      "--len": c.len,
      "--calm-sky": calmBackground(COLOR_SCRIPT[index], false),
      "--calm-sky-ok": calmBackground(COLOR_SCRIPT[index], true),
    } as Vars,
    "aria-labelledby": `cw-h-${c.key}`,
    ...(index === 0 ? { "data-on": "" } : {}),
  };
};

/* Example data shown in the story. Labelled as examples on the page. */
const STORM = [
  { t: "6h 12m", x: 16, y: 44, z: -300 }, { t: "Day 18", x: 76, y: 40, z: -520 }, { t: "1.4 L", x: 30, y: 74, z: -760 },
  { t: "72 bpm", x: 84, y: 66, z: -980 }, { t: "7,840 steps", x: 12, y: 58, z: -1220 }, { t: "mood 3 of 5", x: 62, y: 84, z: -1440 },
  { t: "118/76", x: 40, y: 46, z: -1680 }, { t: "2 headaches", x: 88, y: 50, z: -1900 }, { t: "3 coffees", x: 22, y: 88, z: -2120 },
  { t: "5h 40m", x: 66, y: 52, z: -2340 }, { t: "cramps", x: 34, y: 60, z: -2560 }, { t: "58.2 kg", x: 78, y: 88, z: -2780 },
  { t: "low energy", x: 8, y: 40, z: -3000 }, { t: "Day 26", x: 56, y: 66, z: -3220 }, { t: "9,102 steps", x: 92, y: 36, z: -3440 },
  { t: "0.6 L", x: 44, y: 78, z: -3660 },
];

const PHASES = [
  { key: "period", name: "Period", days: "Days 1 to 5", a: 0.04, b: 0.145, color: "#E8336F",
    copy: "Log flow, cramps and energy in a sentence. Bubbles keeps count of how long your periods last." },
  { key: "follicular", name: "Follicular", days: "Days 6 to 13", a: 0.145, b: 0.29, color: "#FF8A7A",
    copy: "Some people feel their energy lift after a period. Bubbles checks whether that is true for you." },
  { key: "ovulation", name: "Ovulation", days: "Around day 14", a: 0.29, b: 0.355, color: "#FFC37A",
    copy: "Bubbles can estimate a window from your own history. It is an estimate, never birth control." },
  { key: "luteal", name: "Luteal", days: "Days 17 to 28", a: 0.355, b: 0.64, color: "#B49BFF",
    copy: "Sleep, cravings and mood can shift before a period. Bubbles compares this cycle with your past ones." },
];

/* Six past cycles: where a headache was logged (degrees on the ring, 0 = top, clockwise). */
const RINGS = [
  { r: 62, from: 140, to: -26, hit: true },
  { r: 86, from: -120, to: -26, hit: true },
  { r: 110, from: 60, to: 95, hit: false },
  { r: 134, from: 200, to: -26, hit: true },
  { r: 158, from: -70, to: 150, hit: false },
  { r: 182, from: 100, to: -26, hit: true },
];

const ZOOM = [
  { key: "today", title: "Today." },
  { key: "week", title: "This week." },
  { key: "season", title: "This season." },
  { key: "story", title: "Your story." },
];

const LAYERS = [
  { level: "L0", title: "Right now", body: "What you are telling Bubbles in this conversation." },
  { level: "L1", title: "Things you logged", body: "Symptoms, sleep, water and more, each with a date." },
  { level: "L2", title: "Facts about you", body: "Conditions, allergies and medications you confirmed." },
  { level: "L3", title: "Patterns it noticed", body: "Links across signals, with how sure Bubbles is." },
  { level: "L4", title: "Your core profile", body: "The basics that make every answer personal." },
];

const STATEMENTS = [
  { title: "Red flags first.", body: "Urgent symptoms get clear, urgent guidance from fixed safety rules, before any AI is involved." },
  { title: "Shows its sources.", body: "Health guidance is grounded in trusted references, and Bubbles tells you which ones it used." },
  { title: "Yours alone.", body: "Every record is locked to your account. Bubbles asks before anything becomes memory." },
  { title: "Honest when unsure.", body: "Bubbles says how confident it is, points out missing data, and never diagnoses." },
  { title: "Ready for your doctor.", body: "Walk into appointments with your history, patterns and questions already in order." },
];

export function Landing() {
  return (
    <div className={`cw ${display.variable} ${mono.variable}`} data-tone="light" data-active="enter" style={ROOT_VARS}>
      <a href="#main" className="cw-skip">Skip to content</a>
      <noscript
        dangerouslySetInnerHTML={{
          __html: '<style>.cw .cw-ch{height:auto!important}.cw .cw-layer{position:relative!important;visibility:visible!important}</style>',
        }}
      />
      <ScrollDirector />

      <div className="cw-bg" aria-hidden="true">
        <SkyMount />
      </div>
      <div className="cw-portal cw-portal--rim" aria-hidden="true" />
      <div className="cw-portal cw-portal--dive" aria-hidden="true" />
      <div className="cw-portal cw-portal--bloom" aria-hidden="true" />
      <WorldMount />
      <TravelRoutes />
      <BubblesHost />
      <div className="cw-grain" aria-hidden="true" />

      <header className="cw-nav">
        <Link href="/" className="cw-nav-home" aria-label="Bubbles home">
          <BubblesLogo size={36} />
        </Link>
        <div className="cw-nav-end">
          <PauseMotion />
          <AuthCta variant="nav" />
        </div>
      </header>

      <ChapterRail />

      <SpeechBubble />

      <main id="main" tabIndex={-1}>
        {/* ── Enter ─────────────────────────────────────────── */}
        <section {...chapter("enter")}>
          <div className="cw-layer cw-back" aria-hidden="true">
            <SoapCss variant="hero" />
            <div className="cw-wordmark">
              {"bubbles".split("").map((ch, i) => (
                <span key={i} style={{ "--i": i } as Vars}>{ch}</span>
              ))}
            </div>
          </div>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <div className="cw-enter-copy">
                <h1 id="cw-h-enter" className="cw-display">
                  Your body keeps a story. <span className="cw-accent">Bubbles remembers&nbsp;it.</span>
                </h1>
                <p className="cw-lede">A cycle-aware health companion that listens, remembers and connects the dots over time.</p>
                <AuthCta variant="hero" />
              </div>
              <div className="cw-calm-bubbles cw-calm-bubbles--enter">
                <BubblesFigure uid="calm-enter" pose="wave" mood="happy" title={BUBBLES_ALT} />
              </div>
            </div>
          </div>
        </section>

        {/* ── Body ──────────────────────────────────────────── */}
        <section {...chapter("body")}>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <div className="cw-body-copy">
                <h2 id="cw-h-body" className="cw-h2 cw-swap">
                  <span className="cw-swap-a">Your body is a living system.</span>{" "}
                  <span className="cw-swap-b">Every part of it is talking.</span>
                </h2>
                <p className="cw-lede">
                  Hormones, sleep, mood, digestion and your heart are always in conversation. A change in one shows up in the others.
                </p>
              </div>
              <SystemLabels />
            </div>
          </div>
        </section>

        {/* ── Numbers ───────────────────────────────────────── */}
        <section {...chapter("noise")}>
          <div className="cw-layer cw-back" aria-hidden="true">
            <div className="cw-storm">
              {STORM.filter((_, i) => i % 2 === 0).map((s) => (
                <span key={s.t} className="cw-token" style={{ "--x": `${s.x}%`, "--y": `${s.y}%`, "--z": s.z } as Vars}>{s.t}</span>
              ))}
            </div>
          </div>
          <div className="cw-layer cw-front">
            <div className="cw-storm" aria-hidden="true">
              {STORM.filter((_, i) => i % 2 === 1).map((s) => (
                <span key={s.t} className="cw-token" style={{ "--x": `${s.x}%`, "--y": `${s.y}%`, "--z": s.z } as Vars}>{s.t}</span>
              ))}
            </div>
            <div className="cw-stage">
              <div className="cw-noise-copy">
                <h2 id="cw-h-noise" className="cw-h2 cw-swap">
                  <span className="cw-swap-a">A number is a moment.</span>{" "}
                  <span className="cw-swap-b">Your health is the story between them.</span>
                </h2>
                <p className="cw-lede">
                  Most apps stop at the number. Bubbles keeps going, so six hours of sleep means something next to your cycle, your stress and your week.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ── Track ─────────────────────────────────────────── */}
        <section {...chapter("track")}>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <h2 id="cw-h-track" className="cw-h2 cw-track-title">Say it the way you would tell a friend.</h2>
              <TypedIntake />
            </div>
          </div>
        </section>

        {/* ── Cycle ─────────────────────────────────────────── */}
        <section {...chapter("cycle")}>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <div className="cw-cycle-copy">
                <h2 id="cw-h-cycle" className="cw-h2">Built around your rhythm, not an average one.</h2>
                <CycleDay />
                <div className="cw-phases">
                  {PHASES.map((ph) => (
                    <article key={ph.key} className="cw-phase" style={{ "--a": ph.a, "--b": ph.b, "--c": phaseInk(ph.color) } as Vars}>
                      <h3>
                        {ph.name} <span className="cw-mono">{ph.days}</span>
                      </h3>
                      <p>{ph.copy}</p>
                    </article>
                  ))}
                </div>
                <p className="cw-fineprint">Example cycle. Every body is different, and Bubbles learns yours.</p>
              </div>

              <figure className="cw-history">
                <svg viewBox="0 0 400 400" role="img" aria-labelledby="cw-history-cap">
                  {RINGS.map((ring, k) => (
                    <g key={ring.r} style={{ "--k": k } as Vars} className="cw-history-ring">
                      <circle cx="200" cy="200" r={ring.r} className="cw-ring-track" />
                      <circle
                        cx="200"
                        cy="200"
                        r={ring.r}
                        className="cw-ring-period"
                        pathLength={28}
                        strokeDasharray="5 23"
                        transform="rotate(-90 200 200)"
                      />
                      <g className="cw-ring-dot" style={{ "--from": `${ring.from}deg`, "--to": `${ring.to}deg` } as Vars} data-hit={ring.hit ? "" : undefined}>
                        <circle cx="200" cy={200 - ring.r} r="6" />
                      </g>
                    </g>
                  ))}
                  {/* day 27 (two days before day 1): -34deg to -18deg from the top */}
                  <path className="cw-history-wedge" d="M200 200 L94.9 44.1 A188 188 0 0 1 141.9 21.2 Z" />
                </svg>
                <figcaption id="cw-history-cap">
                  <span className="cw-mono">Example pattern</span>
                  Headaches showed up in the two days before your period in 4 of your last 6 cycles.
                  <small>Bubbles tells you how sure it is, and when it is worth asking a clinician.</small>
                </figcaption>
              </figure>
            </div>
          </div>
        </section>

        {/* ── Connect ───────────────────────────────────────── */}
        <section {...chapter("connect")}>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <h2 id="cw-h-connect" className="cw-h2 cw-connect-title">Everything you track is connected. Bubbles notices how.</h2>
              <ConnectWeb />
            </div>
          </div>
        </section>

        {/* ── Memory ────────────────────────────────────────── */}
        <section {...chapter("remember")}>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <h2 id="cw-h-remember" className="cw-h2 cw-zoom-title">
                <span className="cw-sr">Bubbles remembers your health over time: </span>
                {ZOOM.map((z, k) => (
                  <span key={z.key} className="cw-zoom-word" style={{ "--k": k } as Vars}>
                    {z.title}
                  </span>
                ))}
              </h2>

              <div className="cw-zoom" aria-hidden="true">
                <ZoomToday />
                <ZoomWeek />
                <ZoomSeason />
                <ZoomStory />
              </div>

              <div className="cw-memory-side">
                <ol className="cw-layers" aria-label="Bubbles' five layers of memory">
                  {LAYERS.map((layer, k) => (
                    <li key={layer.level} style={{ "--k": k } as Vars}>
                      <span className="cw-mono">{layer.level}</span>
                      <strong>{layer.title}</strong>
                      <span>{layer.body}</span>
                    </li>
                  ))}
                </ol>
                <p className="cw-lede">Nothing becomes memory until you confirm it. Review, correct or delete anything, any time.</p>
              </div>
            </div>
          </div>
        </section>

        {/* ── Companion ─────────────────────────────────────── */}
        <section {...chapter("companion")}>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <h2 id="cw-h-companion" className="cw-h2 cw-companion-title">Ask anything. Bubbles answers with your whole story in mind.</h2>
              <CompanionDemo />
            </div>
          </div>
        </section>

        {/* ── Care ──────────────────────────────────────────── */}
        <section {...chapter("care")}>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <h2 id="cw-h-care" className="cw-care-title">Cute on the outside. Careful on the inside.</h2>
              <div className="cw-care-track" style={{ "--n": STATEMENTS.length } as Vars}>
                {STATEMENTS.map((s, k) => (
                  <article key={s.title} className="cw-statement" style={{ "--k": k } as Vars}>
                    <h3>{s.title}</h3>
                    <p>{s.body}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── Bubbles ──────────────────────────────────────────── */}
        <section {...chapter("bubbles")}>
          <div className="cw-layer cw-back" aria-hidden="true">
            <div className="cw-final-glow" />
            <SoapCss variant="finale" />
          </div>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <div className="cw-final">
                <h2 id="cw-h-bubbles" className="cw-display">Start your health story with Bubbles.</h2>
                <p className="cw-lede">One message is enough to begin. Bubbles takes it from there.</p>
                <div className="cw-final-actions">
                  <AuthCta variant="final" />
                  {/* The download page, not the APK: people see the install steps first. */}
                  <Link href="/android" className="cw-btn cw-btn--ghost cw-btn--lg">
                    Download for Android
                  </Link>
                </div>
              </div>
              <div className="cw-calm-bubbles cw-calm-bubbles--final" aria-hidden="true">
                <BubblesFigure uid="calm-final" pose="cheer" mood="happy" />
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="cw-footer">
        <div className="cw-footer-inner">
          <BubblesLogo size={30} />
          <p>Bubbles is a wellness companion, not a medical device, and does not diagnose. In an emergency, contact your local emergency number.</p>
          <div className="cw-footer-links">
            <Link href="/login">Sign in</Link>
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
            <Link href="/android">Android app</Link>
            <span>© 2026 Bubbles</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ── Memory zoom levels (decorative; the text above carries the meaning) ── */

function ZoomToday() {
  const pins = [
    { h: 8.2, label: "Cramps", tone: "period" },
    { h: 9.5, label: "Water", tone: "sky" },
    { h: 13, label: "Lunch", tone: "follicular" },
    { h: 18.75, label: "Walk", tone: "ovulation" },
    { h: 23.6, label: "Sleep", tone: "luteal" },
  ];
  return (
    <div className="cw-zl cw-zl-today" style={{ "--k": 0 } as Vars}>
      <div className="cw-axis">
        {[0, 6, 12, 18, 24].map((h) => (
          <span key={h} style={{ "--x": `${(h / 24) * 100}%` } as Vars}>{`${String(h % 24).padStart(2, "0")}:00`}</span>
        ))}
      </div>
      {pins.map((pin) => (
        <span key={pin.label} className={`cw-pin cw-tone-${pin.tone}`} style={{ "--x": `${(pin.h / 24) * 100}%` } as Vars}>
          {pin.label}
        </span>
      ))}
    </div>
  );
}

function ZoomWeek() {
  const days = [
    { d: "Mon", sleep: 7.4, dot: false }, { d: "Tue", sleep: 6.1, dot: true }, { d: "Wed", sleep: 5.6, dot: true },
    { d: "Thu", sleep: 7.9, dot: false }, { d: "Fri", sleep: 6.4, dot: false }, { d: "Sat", sleep: 8.3, dot: false },
    { d: "Sun", sleep: 5.9, dot: true },
  ];
  return (
    <div className="cw-zl cw-zl-week" style={{ "--k": 1 } as Vars}>
      {days.map((day) => (
        <div key={day.d} className="cw-day">
          {day.dot && <span className="cw-day-dot" />}
          <span className="cw-bar" style={{ "--v": day.sleep / 9 } as Vars} />
          <span className="cw-mono">{day.d}</span>
        </div>
      ))}
      <span className="cw-zl-note cw-mono">Sleep, hours</span>
    </div>
  );
}

function ZoomSeason() {
  const mood = Array.from({ length: 49 }, (_, i) => 50 + 22 * Math.sin(i * 0.42) + 8 * Math.sin(i * 1.3));
  const sleep = Array.from({ length: 49 }, (_, i) => 60 + 16 * Math.sin(i * 0.42 + 1.4) + 6 * Math.cos(i * 0.9));
  const path = (vals: number[]) => vals.map((v, i) => `${i === 0 ? "M" : "L"}${(i / 48) * 1000} ${v}`).join(" ");
  return (
    <div className="cw-zl cw-zl-season" style={{ "--k": 2 } as Vars}>
      <svg viewBox="0 0 1000 120" preserveAspectRatio="none">
        {[0, 1, 2, 3].map((k) => (
          <rect key={k} x={40 + k * 245} y="0" width="44" height="120" className="cw-season-band" />
        ))}
        <path d={path(mood)} className="cw-season-mood" />
        <path d={path(sleep)} className="cw-season-sleep" />
      </svg>
      <div className="cw-season-legend cw-mono">
        <span className="cw-key-period">Period</span>
        <span className="cw-key-mood">Mood</span>
        <span className="cw-key-sleep">Sleep</span>
      </div>
    </div>
  );
}

function ZoomStory() {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return (
    <div className="cw-zl cw-zl-story" style={{ "--k": 3 } as Vars}>
      <div className="cw-months">
        {months.map((m, k) => (
          <span key={m} className="cw-month" style={{ "--k": k } as Vars}>
            <i />
            <span className="cw-mono">{m}</span>
          </span>
        ))}
      </div>
      <p className="cw-callout" style={{ "--x": "22%" } as Vars}>Headaches before periods</p>
      <p className="cw-callout cw-callout--b" style={{ "--x": "64%" } as Vars}>Better sleep after evening walks</p>
    </div>
  );
}
