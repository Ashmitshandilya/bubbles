import type { CSSProperties } from "react";
import Link from "next/link";
import { AuthCta } from "./AuthCta";
import { BubblesLogo } from "./BubblesMark";
import { LandingMascot } from "./LandingMascot";
import { ScrollDirector } from "./story/ScrollDirector";
import { ChapterRail } from "./story/ChapterRail";
import { PauseMotion } from "./story/PauseMotion";
import { COLOR_SCRIPT, PHASE_COLORS } from "./atmosphere/palette";
import { SkyMount } from "./atmosphere/SkyMount";
import { calmBackground, skyVars } from "./atmosphere/sky";
import { CHAPTERS, MOBILE_LEN_FACTOR } from "./story/store";
import { WorldMount } from "./world/WorldMount";
import { RING, THREADS } from "./ring";
import "./landing.css";

/*
 * The Bubbles landing page: one continuous, scroll-driven story in six chapters, in the Pearl Lab look.
 *
 *   enter -> listen -> confirm -> patterns -> prepare -> close
 *
 * Each pinned chapter is a tall section that only provides scroll length; its layers are fixed to the viewport
 * and choreographed by CSS custom properties written by <ScrollDirector/> (--p progress, --in and --out for the
 * hand-overs). One WebGL canvas (<WorldMount/>, lazy) draws the orb, a real thin-film soap bubble, over the
 * box marked `data-orb` in the chapter on stage, plus a few small bubbles. Until it arrives (and in the static
 * tier) the same boxes are CSS bubbles. The close is an ordinary section that scrolls into the footer.
 * With reduced motion (or no JavaScript) the same content renders as a calm, normally scrolling page.
 */

type Vars = CSSProperties & Record<`--${string}`, string | number>;

const ROOT_VARS = { ...skyVars(COLOR_SCRIPT[0]), "--lenk-m": MOBILE_LEN_FACTOR } as Vars;

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

const MASCOT_ALT = "Bubbles, a baby unicorn doctor in a white coat with a lilac stethoscope";

/* Example data shown in the story. Every piece is labelled as an example on the page. */

/** One day, as Bubbles picked it out of a message. `z`: 0 near (front of the orb) .. 1 far (inside it). */
const CHIPS = [
  { kind: "Food", text: "2 rotis, dal and curd", note: "lunch, 1:40 pm", x: 14, y: 30, z: 0 },
  { kind: "Sleep", text: "slept 7h 12m", note: "last night", x: 70, y: 18, z: 0.25 },
  { kind: "Symptom", text: "cramps since morning", note: "today", x: 64, y: 70, z: 0.1 },
  { kind: "Water", text: "water 5 of 8", note: "glasses so far", x: 22, y: 78, z: 0.35 },
];
const FAR_CHIPS = [
  { text: "cycle day 2", x: 42, y: 46, z: 0.8 },
  { text: "walked 20 min", x: 58, y: 40, z: 1 },
];

const SUMMARY = [
  ["Cycles tracked", "6"],
  ["Average cycle length", "29 days (varies by about 2 days)"],
  ["Average period length", "5 days"],
  ["Last period started", "2 Oct 2026"],
  ["Next period (estimate)", "31 Oct 2026"],
] as const;

const SYMPTOMS = [
  ["Cramps", "14 days"],
  ["Low energy", "9 days"],
  ["Headache", "6 days"],
] as const;

/** The privacy promises, each one true today (app/privacy). */
const PROMISES = [
  {
    title: "Nothing becomes memory until you confirm it.",
    body: "You see what Bubbles understood before anything is saved, and you can delete any entry later.",
  },
  {
    title: "You choose what a partner sees.",
    body: "Partner sharing is off until you turn it on. Then one person sees only the summaries you pick. Chats and symptoms are never shared.",
  },
  {
    title: "No ads, no tracking cookies, no analytics.",
    body: "Request logs are designed to leave your messages out.",
  },
];

export function Landing() {
  return (
    <div className="cw" data-tone="light" data-active="enter" style={ROOT_VARS}>
      <a href="#main" className="cw-skip">Skip to content</a>
      <noscript
        dangerouslySetInnerHTML={{
          __html: '<style>.cw .cw-ch{height:auto!important}.cw .cw-layer{position:relative!important;visibility:visible!important;opacity:1!important}</style>',
        }}
      />
      <ScrollDirector />

      <div className="cw-bg" aria-hidden="true">
        <SkyMount />
      </div>
      <WorldMount />
      <div className="cw-grain" aria-hidden="true" />

      <header className="cw-nav">
        <Link href="/" className="cw-nav-home" aria-label="Bubbles home">
          <BubblesLogo size={34} />
        </Link>
        <div className="cw-nav-end">
          <PauseMotion />
          <AuthCta variant="nav" />
        </div>
      </header>

      <ChapterRail />

      <main id="main" tabIndex={-1}>
        {/* 1. Opening: the orb, with Bubbles inside it */}
        <section {...chapter("enter")}>
          <div className="cw-layer cw-back">
            <div className="cw-stage">
              <div className="cw-orb cw-hero-orb" data-orb>
                <span className="cw-orb-caustic" aria-hidden="true" />
                <LandingMascot pose="idle" size={420} className="cw-hero-mascot" title={MASCOT_ALT} />
              </div>
            </div>
          </div>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <div className="cw-copy cw-hero-copy">
                <h1 id="cw-h-enter" className="cw-display">
                  Your body keeps a story. <span className="cw-accent">Bubbles remembers&nbsp;it.</span>
                </h1>
                <p className="cw-lede">
                  Tell Bubbles about your day in your own words. It keeps what you confirm and shows you how your cycle, sleep and mood move together over time.
                </p>
                <AuthCta variant="hero" />
              </div>
              <p className="cw-cue cw-mono" aria-hidden="true">Scroll</p>
            </div>
          </div>
        </section>

        {/* 2. Just talk: a day's details floating in the orb at different depths */}
        <section {...chapter("listen")}>
          <div className="cw-layer cw-back" aria-hidden="true">
            <div className="cw-stage">
              <div className="cw-orb cw-listen-orb" data-orb>
                {FAR_CHIPS.map((c) => (
                  <span key={c.text} className="cw-chip cw-chip--far" style={{ "--x": `${c.x}%`, "--y": `${c.y}%`, "--z": c.z } as Vars}>
                    {c.text}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <div className="cw-copy cw-listen-copy">
                <h2 id="cw-h-listen" className="cw-h2">Just talk. Bubbles listens.</h2>
                <p className="cw-lede">Write it the way you would tell a friend. Bubbles picks out the food, sleep, symptoms and water in what you say.</p>
              </div>
              <div className="cw-listen-field">
                <ul className="cw-chips" aria-label="Example: what Bubbles picked out of one message">
                  {CHIPS.map((c, k) => (
                    <li key={c.text} className="cw-chip" style={{ "--x": `${c.x}%`, "--y": `${c.y}%`, "--z": c.z, "--k": k } as Vars}>
                      <span className="cw-mono">{c.kind}</span>
                      <strong>{c.text}</strong>
                      <span className="cw-mono">{c.note}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <p className="cw-say">
                <span className="cw-mono">Example message</span>
                Lunch was 2 rotis, dal and curd. Cramps since morning. Slept 7h 12m, and I am on glass 5 of 8.
              </p>
            </div>
          </div>
        </section>

        {/* 3. Confirm: the chat and the confirm card */}
        <section {...chapter("confirm")}>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <div className="cw-copy cw-confirm-copy">
                <h2 id="cw-h-confirm" className="cw-h2">Nothing becomes memory until you confirm&nbsp;it.</h2>
                <p className="cw-lede">Bubbles shows you what it understood. Confirm it, or edit it first. What you skip is never saved.</p>
              </div>
              <figure className="cw-chat" aria-labelledby="cw-chat-cap">
                <div className="cw-orb cw-confirm-orb" data-orb aria-hidden="true" />
                <figcaption id="cw-chat-cap" className="cw-mono">Example conversation</figcaption>
                <p className="cw-msg cw-msg--you">Lunch was 2 rotis, dal and curd. Cramps since morning. Slept 7h 12m.</p>
                <div className="cw-msg cw-msg--bubbles">
                  <span className="cw-avatar" aria-hidden="true">
                    <BubblesLogo size={28} className="cw-avatar-mark" />
                  </span>
                  <p>Thanks for telling me. I picked out three things. Should I save them to your health record?</p>
                </div>
                <div className="cw-card">
                  <ul>
                    <li>
                      <span className="cw-mono">Food</span>
                      <strong>2 rotis, dal and curd</strong>
                      <span className="cw-mono">today, lunch</span>
                    </li>
                    <li>
                      <span className="cw-mono">Symptom</span>
                      <strong>Cramps</strong>
                      <span className="cw-mono">since this morning</span>
                    </li>
                    <li>
                      <span className="cw-mono">Sleep</span>
                      <strong>7h 12m</strong>
                      <span className="cw-mono">last night</span>
                    </li>
                  </ul>
                  <div className="cw-card-actions">
                    <span className="cw-fake-btn cw-fake-btn--primary">Confirm</span>
                    <span className="cw-fake-btn">Edit</span>
                  </div>
                  <p className="cw-saved">Saved. Three entries added to your memory.</p>
                </div>
              </figure>
            </div>
          </div>
        </section>

        {/* 4. Patterns: the cycle ring with sleep, mood and energy threads */}
        <section {...chapter("patterns")}>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <div className="cw-copy cw-patterns-copy">
                <h2 id="cw-h-patterns" className="cw-h2">Patterns across weeks, not&nbsp;days.</h2>
                <p className="cw-lede">One bad night is just a night. Bubbles waits until something repeats across your cycles, then tells you how sure it is.</p>
                <p className="cw-note">
                  <span className="cw-mono">Example pattern, medium confidence</span>
                  Your energy was lower in the three days before your period in 3 of your last 4 cycles.
                </p>
                <p className="cw-fineprint">Cycle phases are an estimate, never birth control.</p>
              </div>
              <figure className="cw-ring">
                <svg viewBox="0 0 560 560" role="img" aria-labelledby="cw-ring-cap">
                  <defs>
                    <linearGradient id="cw-ring-glass" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.95" />
                      <stop offset="0.55" stopColor="#F3ECFB" stopOpacity="0.75" />
                      <stop offset="1" stopColor="#FFFFFF" stopOpacity="0.9" />
                    </linearGradient>
                  </defs>
                  <circle cx={RING.c} cy={RING.c} r={RING.r} className="cw-ring-glass" stroke="url(#cw-ring-glass)" />
                  <circle cx={RING.c} cy={RING.c} r={RING.r + RING.w / 2} className="cw-ring-edge" />
                  <circle cx={RING.c} cy={RING.c} r={RING.r - RING.w / 2} className="cw-ring-edge" />
                  {RING.phases.map((ph, k) => (
                    <g key={ph.key} className="cw-ring-phase" style={{ "--k": k } as Vars}>
                      <path d={ph.arc} stroke={PHASE_COLORS[ph.key]} pathLength={1} />
                      <circle cx={ph.dot[0]} cy={ph.dot[1]} r="6" fill={PHASE_COLORS[ph.key]} />
                      <text x={ph.label[0]} y={ph.label[1]} textAnchor={ph.anchor} dominantBaseline="middle">
                        {ph.name}
                      </text>
                    </g>
                  ))}
                  <path d={RING.dip} className="cw-ring-dip" />
                  {THREADS.map((t, k) => (
                    <g key={t.key} className={`cw-thread cw-thread--${t.key}`} style={{ "--k": k } as Vars}>
                      <mask id={`cw-thread-${t.key}`} maskUnits="userSpaceOnUse" x="0" y="0" width="560" height="560">
                        {t.paths.map((d, i) => (
                          <path key={i} d={d} pathLength={1} className="cw-reveal" />
                        ))}
                      </mask>
                      <g mask={`url(#cw-thread-${t.key})`}>
                        {t.paths.map((d, i) => (
                          <path key={i} d={d} className="cw-line" />
                        ))}
                      </g>
                    </g>
                  ))}
                  <text x={RING.c} y={RING.c - 10} textAnchor="middle" className="cw-ring-num">3 of 4</text>
                  <text x={RING.c} y={RING.c + 26} textAnchor="middle" className="cw-ring-sub">cycles with the same dip</text>
                </svg>
                <figcaption id="cw-ring-cap">
                  <span className="cw-sr">
                    Example cycle ring: four phases, period, follicular, ovulation and luteal, with sleep, mood and energy drawn around them for one cycle.
                    Energy dips in the last three days, the pattern seen in 3 of 4 cycles. Two days of mood were not logged and are left as a gap.
                  </span>
                  <span className="cw-legend" aria-hidden="true">
                    {THREADS.map((t) => (
                      <span key={t.key} className={`cw-legend-${t.key}`}>
                        <i />
                        {t.label}
                      </span>
                    ))}
                    <span className="cw-legend-gap">gap: not logged</span>
                  </span>
                </figcaption>
              </figure>
            </div>
          </div>
        </section>

        {/* 5. Prepare: the summary for a clinician */}
        <section {...chapter("prepare")}>
          <div className="cw-layer cw-front">
            <div className="cw-stage">
              <div className="cw-copy cw-prepare-copy">
                <h2 id="cw-h-prepare" className="cw-h2">Walk into your appointment prepared.</h2>
                <p className="cw-lede">
                  Bubbles turns what you logged into one page for your doctor: your cycles, symptoms, pain and the questions you want to ask. Print it or save it as a PDF.
                </p>
                <p className="cw-strong">Bubbles does not diagnose. It organises what you told it.</p>
              </div>
              <figure className="cw-sheet" aria-labelledby="cw-sheet-title">
                <span className="cw-mono cw-sheet-tag">Example</span>
                <h3 id="cw-sheet-title">Cycle summary for my clinician</h3>
                <p className="cw-mono">Prepared with Bubbles, covers Apr to Sep 2026</p>
                <p className="cw-sheet-note">Organised from my own logs. Not a diagnosis.</p>
                <dl>
                  {SUMMARY.map(([k, v]) => (
                    <div key={k}>
                      <dt>{k}</dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>
                <h4>Symptoms logged</h4>
                <dl className="cw-sheet-symptoms">
                  {SYMPTOMS.map(([k, v]) => (
                    <div key={k}>
                      <dt>{k}</dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>
                <h4>Questions I might ask</h4>
                <ol>
                  <li>Is cramping on the first two days worth looking into?</li>
                  <li>Could my lower energy before periods be linked to my sleep?</li>
                </ol>
                <p className="cw-sheet-foot">Predictions are estimates from self-reported logs. They are not birth control and they do not replace medical advice.</p>
              </figure>
            </div>
          </div>
        </section>

        {/* 6. Close: three promises, one call to action */}
        <section {...chapter("close")}>
          <div className="cw-stage cw-close-stage">
            <div className="cw-orb cw-close-orb" data-orb aria-hidden="true">
              <span className="cw-orb-caustic" />
              <LandingMascot pose="wave" size={300} className="cw-close-mascot" />
            </div>
            <div className="cw-copy cw-close-copy">
              <h2 id="cw-h-close" className="cw-h2">Start your story with Bubbles.</h2>
              <ol className="cw-promises">
                {PROMISES.map((p) => (
                  <li key={p.title}>
                    <h3>{p.title}</h3>
                    <p>{p.body}</p>
                  </li>
                ))}
              </ol>
              <AuthCta variant="final" />
            </div>
          </div>
        </section>
      </main>

      <footer className="cw-footer">
        <div className="cw-footer-inner">
          <BubblesLogo size={28} />
          <p>Bubbles is a wellness companion, not a medical device, and does not diagnose. In an emergency, contact your local emergency number.</p>
          <div className="cw-footer-links">
            <Link href="/login">Sign in</Link>
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
            <Link href="/android">Android app</Link>
            <a href="mailto:hello@heybubbles.in">hello@heybubbles.in</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
