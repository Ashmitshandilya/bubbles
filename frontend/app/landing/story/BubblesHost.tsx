"use client";

import { useEffect, useRef, type CSSProperties } from "react";
import { BubblesFigure } from "../BubblesFigure";
import { BubbleLocket } from "../bubbles/BubbleLocket";
import { HOP_LIFT_PX, RIGS, type Env, type Rig } from "../world/rig";
import { feelAt, feelBand, type FeelBand } from "./feel";
import { CHAPTER_INDEX, NEVER, easeInOut, hopT, isLead, lerp, onStoryFrame, range, say, story, trackSpeed } from "./store";

/**
 * The host of the story: the illustrated Bubbles, placed on the stage every frame.
 * With the 3D world running it stands exactly where the world's (invisible)
 * Bubbles anchor is, so the bead halo and orbit wrap around it; without WebGL it
 * follows the chapter choreography directly.
 *
 * Behaviour, in priority order (later wins): chapter pose and gaze, travel
 * (flying, the carry hop, walking the memory road), mirroring the cycle's inner
 * weather, dozing off when the page is left alone, perking up at the start
 * buttons, and the boop.
 */

const VIEW_W = 360;
const VIEW_H = 520;
const FIGURE_H = 443; // horn tip (y 63) to hooves (y 506) inside the viewBox
const BODY_UNITS = 2.42; // the same height in world units at scale 1
const PELVIS_Y = 426; // pelvis line inside the viewBox
const PELVIS_X = 175;
const HOOF_BELOW_PELVIS = 80; // viewBox units

type Pose = "idle" | "wave" | "point" | "present" | "think" | "cheer" | "surprised" | "fly";
type Vars = CSSProperties & Record<`--${string}`, string | number>;

function figurePose(name: Rig["bubbles"]["pose"]): { pose: Pose; face: number } {
  switch (name) {
    case "pointA":
      return { pose: "point", face: 1 };
    case "pointB":
    case "pointUpB":
      return { pose: "point", face: -1 };
    case "lookBack":
      return { pose: "idle", face: -1 };
    case "sit":
      return { pose: "idle", face: 0 };
    case "wave":
    case "present":
    case "think":
    case "cheer":
    case "surprised":
    case "fly":
      return { pose: name, face: 0 };
    default:
      return { pose: "idle", face: 0 };
  }
}

const MOOD: Record<Pose, string> = {
  idle: "calm", wave: "happy", point: "calm", present: "happy", think: "calm", cheer: "happy", surprised: "surprised", fly: "calm",
};

/* Heart burst from the horn tip: six hearts and two sparkles, fanned out. */
const SPARKS = Array.from({ length: 8 }, (_, k) => {
  const spread = (k / 7) * 2 - 1;
  return {
    heart: k < 6,
    dx: Math.round(spread * 46),
    dy: -60 - Math.round(Math.abs(Math.sin(k * 1.7)) * 36),
    r: Math.round(spread * 15),
    d: (k % 4) * 40,
  };
});

export function BubblesHost() {
  const wrap = useRef<HTMLDivElement>(null);
  const figure = useRef<HTMLDivElement>(null);
  const sparks = useRef<HTMLDivElement>(null);
  const boopAt = useRef(NEVER);
  const hovered = useRef(false);

  useEffect(() => {
    const start = performance.now();
    const sim = { x: 0, y: 0, h: 0, init: false, face: 1, lean: 0, vx: 0 };
    let lastPose = "";
    let lastMood = "";
    let lastWag = "";
    let lastWalk = "";
    let lastSleep = "";
    let lastFace = 0;
    let lastShow = "";
    let lastLocket = "";
    let lastLive = false;
    // travel one-shots
    let lastHop = 0;
    let whee = false;
    let landAt = 0;
    // inner weather
    let lastBand: FeelBand | "" = "";
    let happyUntil = 0;
    // wind in the mane (spring)
    let lastY = story.y;
    let wind = 0;
    let windV = 0;
    let lastWind = 0;
    // forty winks
    let lastActive = start;
    let lastPx = story.pointer.x;
    let lastPy = story.pointer.y;
    let wasSleepy = false;
    let wakeAt = -10000;
    let saidWake = false;
    // start buttons
    let cta: Element | null = null;
    let ctaAt = -10000;
    let ctaTimer = 0;

    const root = document.querySelector<HTMLElement>(".cw");
    const onOver = (event: Event) => {
      const button = (event.target as Element | null)?.closest?.(".cw-btn--primary") ?? null;
      if (!button) return;
      window.clearTimeout(ctaTimer);
      if (cta !== button) ctaAt = performance.now();
      cta = button;
    };
    const onOut = (event: Event) => {
      const button = (event.target as Element | null)?.closest?.(".cw-btn--primary");
      if (!button) return;
      window.clearTimeout(ctaTimer);
      ctaTimer = window.setTimeout(() => {
        cta = null;
      }, 120);
    };
    root?.addEventListener("pointerover", onOver);
    root?.addEventListener("focusin", onOver);
    root?.addEventListener("pointerout", onOut);
    root?.addEventListener("focusout", onOut);

    const burst = (one: boolean, big: boolean) => {
      const el = sparks.current;
      if (!el) return;
      el.dataset.burst = el.dataset.burst === "a" ? "b" : "a";
      el.toggleAttribute("data-one", one);
      el.toggleAttribute("data-big", big);
    };
    const onBoop = (event: Event) => {
      const n = (event as CustomEvent<number>).detail ?? 1;
      lastActive = performance.now();
      burst(false, n % 5 === 0);
    };
    const onSpark = () => burst(true, false);
    // Taps and key presses are activity too (they neither scroll nor move a pointer).
    const onActivity = () => {
      lastActive = performance.now();
    };
    window.addEventListener("bubbles:boop", onBoop);
    window.addEventListener("bubbles:spark", onSpark);
    window.addEventListener("pointerdown", onActivity, { passive: true });
    window.addEventListener("keydown", onActivity);

    const anchorFromRig = (r: Rig) => {
      // Without the 3D world: screen anchors directly; the ring position is approximated.
      const vw = story.vw;
      const vh = story.vh;
      const unit = vh / (2 * Math.tan((r.fov * Math.PI) / 360) * Math.max(4, r.bubbles.mode === "ring" ? 10 : r.bubbles.z));
      if (r.bubbles.mode === "ring") return { x: vw * (story.mobile ? 0.5 : 0.66), y: vh * (story.mobile ? 0.22 : 0.3), unit: unit * r.bubbles.scale };
      return { x: ((r.bubbles.x + 1) / 2) * vw, y: ((1 - r.bubbles.y) / 2) * vh, unit: unit * r.bubbles.scale };
    };

    const stop = onStoryFrame((dt) => {
      const w = wrap.current;
      const f = figure.current;
      const svg = f?.querySelector<SVGSVGElement>("svg");
      if (!w || !f || !svg) return;
      const now = performance.now();
      const i = story.current;
      const j = Math.min(i + 1, RIGS.length - 1);
      const t = easeInOut(story.blend);
      const env: Env = { mobile: story.mobile, aspect: story.vw / Math.max(1, story.vh), time: now / 1000, intro: (now - start) / 1000 };
      const A = RIGS[i](story.chapters[i].p, env);
      const B = RIGS[j](story.chapters[j].p, env);
      const lead = t < 0.5 ? A : B;
      const h = hopT();
      const hopChapter = i === CHAPTER_INDEX.track;
      const stiff = lerp(A.bubbles.stiff ?? 0, B.bubbles.stiff ?? 0, t);

      /* ── Where to stand, and how big ── */
      let gx: number;
      let gy: number;
      let unit: number;
      const live = story.worldReady && story.bubbles.anchor.unit > 0;
      if (live) {
        gx = story.bubbles.anchor.x;
        gy = story.bubbles.anchor.y;
        unit = story.bubbles.anchor.unit;
      } else {
        const a = anchorFromRig(A);
        const b = anchorFromRig(B);
        const lift = HOP_LIFT_PX[story.mobile ? "mobile" : "desktop"];
        const arc = (u: number) => (hopChapter ? 4 * u * (1 - u) : 0);
        gx = a.x + (b.x - a.x) * t + lift[0] * story.vw * arc(t);
        gy = a.y + (b.y - a.y) * t + lift[1] * story.vh * arc(t);
        unit = a.unit + (b.unit - a.unit) * t;
        // Without the world, the host publishes the carry-hop route itself.
        const hop = story.hop;
        if (hopChapter && (story.chapters[i].p > 0.86 || story.blend > 0)) {
          const n = hop.n - 1;
          for (let k = 0; k <= n; k += 1) {
            const u = k / n;
            hop.pts[k * 2] = a.x + (b.x - a.x) * u + lift[0] * story.vw * arc(u);
            hop.pts[k * 2 + 1] = a.y + (b.y - a.y) * u + lift[1] * story.vh * arc(u);
          }
          hop.head = story.blend > 0 ? t : 0;
          hop.dest.x = hop.pts[n * 2];
          hop.dest.y = hop.pts[n * 2 + 1];
          hop.live = true;
        } else {
          hop.live = false;
        }
      }
      const rate = h > 0 && h < 1 ? 12 : 4 + 8 * stiff;
      const k = sim.init && !story.worldReady ? 1 - Math.exp(-rate * dt) : 1;
      const px = sim.x;
      sim.x += (gx - sim.x) * k;
      sim.y += (gy - sim.y) * k;
      sim.h += (unit * BODY_UNITS - sim.h) * (sim.init ? 1 - Math.exp(-6 * dt) : 1);
      // A fresh sprite (first frame, or the 3D anchor taking over) has not travelled: no speed spike, no "fly" flash.
      sim.vx = trackSpeed(sim.vx, sim.init && live === lastLive ? px : null, sim.x, dt);
      sim.init = true;
      lastLive = live;

      /* ── Activity (for forty winks) and scroll speed (for the wind) ── */
      const scrolled = Math.abs(story.y - lastY) > 0.5;
      const pointerMoved = story.pointer.x !== lastPx || story.pointer.y !== lastPy;
      if (scrolled || pointerMoved || cta) lastActive = now;
      lastPx = story.pointer.x;
      lastPy = story.pointer.y;
      const v = (story.y - lastY) / Math.max(dt, 1e-3) / Math.max(1, story.vh);
      lastY = story.y;
      const windTarget = Math.max(-1, Math.min(1, v * 0.35));
      windV += ((windTarget - wind) * 60 - windV * 9) * dt;
      wind += windV * dt;
      if (Math.abs(wind - lastWind) > 0.004) {
        svg.style.setProperty("--wind", wind.toFixed(3));
        lastWind = wind;
      }

      /* ── Pose, facing and mood ── */
      const mapped = figurePose(lead.bubbles.pose);
      let pose: Pose = mapped.pose;
      // Face what Bubbles is showing; otherwise face toward the middle of the screen.
      let face =
        mapped.face ||
        (lead.bubbles.turn > 0.15 ? 1 : lead.bubbles.turn < -0.15 ? -1 : sim.x > story.vw * 0.56 ? -1 : sim.x < story.vw * 0.44 ? 1 : sim.face);
      if (i === 0 && now - start < 3600 && story.chapters[0].p < 0.2) pose = "wave";
      if (story.gaze && i === CHAPTER_INDEX.connect && t < 0.5) {
        pose = "point";
        face = story.gaze.side;
      }
      const walking =
        !story.mobile && i === CHAPTER_INDEX.remember && story.blend < 0.02 && Math.abs(sim.vx) > story.vw * 0.04;
      const travelling = !walking && Math.abs(sim.vx) > story.vw * 0.35;
      if (travelling) {
        pose = "fly";
        face = sim.vx > 0 ? 1 : -1;
      }
      const hopFly = h > 0.02 && h < 0.97;
      if (hopFly) {
        pose = "fly";
        face = sim.vx > 20 ? 1 : sim.vx < -20 ? -1 : sim.face;
      }
      if (walking) {
        pose = "idle";
        face = sim.vx > 0 ? 1 : -1;
      }

      let mood = MOOD[pose];
      // Inner weather: on the ring, Bubbles quietly mirrors how the day felt.
      let wag = "0";
      if (isLead(CHAPTER_INDEX.cycle) && lead.bubbles.mode === "ring") {
        const m = feelAt(range(story.chapters[CHAPTER_INDEX.cycle].p, 0.04, 0.62) * 27.999);
        const band = feelBand(m);
        if (band === "bright" && lastBand !== "bright") happyUntil = now + 900;
        lastBand = band;
        mood = band === "heavy" ? "soft" : now < happyUntil ? "happy" : "calm";
        wag = band === "bright" ? "1" : "0";
      }
      if (hopFly) mood = "happy";

      // Forty winks: left alone for a while, Bubbles dozes off; any activity wakes it.
      const sleepy =
        now - start > 20000 &&
        now - lastActive > 14000 &&
        document.visibilityState === "visible" &&
        !travelling &&
        !hopFly &&
        !walking;
      if (sleepy) mood = "sleepy";
      if (wasSleepy && !sleepy) {
        wakeAt = now;
        if (!saidWake) {
          saidWake = true;
          say("Oh! I'm up. Just resting my eyes.", 2600);
        }
      }
      wasSleepy = sleepy;
      if (now - wakeAt < 450) {
        pose = "surprised";
        mood = "surprised";
      }

      // Start buttons: Bubbles turns to them, brightens, and cheers in the hero and finale.
      let ctaTarget: { x: number; y: number } | null = null;
      if (cta) {
        const r = cta.getBoundingClientRect();
        ctaTarget = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        if (!hopFly && !walking) face = ctaTarget.x > sim.x ? 1 : -1;
        mood = "happy";
        if ((isLead(CHAPTER_INDEX.bubbles) || isLead(0)) && now - ctaAt < 650) pose = "cheer";
      }
      story.excite += ((cta && isLead(CHAPTER_INDEX.bubbles) ? 1 : 0) - story.excite) * (1 - Math.exp(-6 * dt));

      const sinceBoop = (now - boopAt.current) / 1000;
      if (sinceBoop < 1.5) {
        pose = "cheer";
        mood = "happy";
      } else if (hovered.current && !sleepy) {
        mood = "happy";
      }
      sim.face = face;
      const leanTarget = walking ? 3 * face : travelling ? Math.max(-12, Math.min(12, (sim.vx / story.vw) * 6)) : 0;
      sim.lean += (leanTarget - sim.lean) * (1 - Math.exp(-5 * dt));

      if (pose !== lastPose) {
        svg.dataset.pose = pose;
        lastPose = pose;
      }
      if (mood !== lastMood) {
        svg.dataset.mood = mood;
        lastMood = mood;
      }
      if (wag !== lastWag) {
        svg.dataset.wag = wag;
        lastWag = wag;
      }
      const walkAttr = walking ? "1" : "0";
      if (walkAttr !== lastWalk) {
        w.dataset.walk = walkAttr;
        lastWalk = walkAttr;
      }
      const sleepAttr = sleepy ? "1" : "0";
      if (sleepAttr !== lastSleep) {
        w.dataset.sleep = sleepAttr;
        lastSleep = sleepAttr;
      }
      if (face !== lastFace) {
        w.style.setProperty("--face", String(face));
        lastFace = face;
      }

      // Carry hop one-shots (forward only).
      if (!whee && lastHop < 0.08 && h >= 0.08) {
        whee = true;
        say("Wheee!", 1400);
      }
      if (lastHop > 0 && lastHop < 0.96 && h >= 0.96) {
        w.dataset.land = "1";
        landAt = now;
      }
      if (landAt && now - landAt > 520) {
        delete w.dataset.land;
        landAt = 0;
      }
      lastHop = h;

      /* ── Eyes: the start button, the pointer, or what Bubbles is presenting ── */
      const headX = sim.x;
      const headY = sim.y - sim.h * 0.66;
      let lx = 0;
      let ly = 0;
      const target = ctaTarget
        ? ctaTarget
        : story.pointer.has && (lead.bubbles.look === "pointer" || lead.bubbles.look === "camera")
          ? { x: ((story.pointer.x + 1) / 2) * story.vw, y: ((1 - story.pointer.y) / 2) * story.vh }
          : story.gaze
            ? { x: ((story.gaze.x + 1) / 2) * story.vw, y: ((1 - story.gaze.y) / 2) * story.vh }
            : null;
      if (target) {
        const dx = target.x - headX;
        const dy = headY - target.y;
        const len = Math.max(60, Math.hypot(dx, dy));
        lx = (dx / len) * face;
        ly = dy / len;
      } else if (lead.bubbles.look === "up") {
        ly = 0.8;
      }
      svg.style.setProperty("--look-x", lx.toFixed(2));
      svg.style.setProperty("--look-y", ly.toFixed(2));

      /* ── Place the figure: the pelvis point of the drawing sits on the anchor ── */
      const scale = sim.h / FIGURE_H;
      w.style.width = `${(VIEW_W * scale).toFixed(1)}px`;
      w.style.height = `${(VIEW_H * scale).toFixed(1)}px`;
      w.style.transform = `translate3d(${(sim.x - PELVIS_X * scale).toFixed(1)}px, ${(sim.y - PELVIS_Y * scale).toFixed(1)}px, 0) rotate(${sim.lean.toFixed(2)}deg)`;
      f.style.transform = `scaleX(${face})`;
      const show = lead.bubbles.show > 0.5 && sim.h > 20 ? "1" : "0";
      if (show !== lastShow) {
        w.dataset.show = show;
        lastShow = show;
      }
      // The locket (a soap bubble round Bubbles) holds her through chapters 2 to 8; the hero and the finale show the full painting.
      const leadIndex = t < 0.5 ? i : j;
      const locket = leadIndex >= 1 && leadIndex <= 7 ? "1" : "0";
      if (locket !== lastLocket) {
        w.dataset.locket = locket;
        lastLocket = locket;
      }

      // Publish head, horn and hooves for the bubble, the companion streams and the routes.
      story.bubbles.x = sim.x + face * 20 * scale;
      story.bubbles.y = sim.y - 300 * scale;
      story.bubbles.horn.x = sim.x + face * 61 * scale;
      story.bubbles.horn.y = sim.y - 363 * scale;
      story.bubbles.feet.x = sim.x;
      story.bubbles.feet.dy = HOOF_BELOW_PELVIS * scale;
      story.bubbles.feet.y = sim.y + story.bubbles.feet.dy;
      story.bubbles.visible = true;
    });

    return () => {
      stop();
      window.clearTimeout(ctaTimer);
      root?.removeEventListener("pointerover", onOver);
      root?.removeEventListener("focusin", onOver);
      root?.removeEventListener("pointerout", onOut);
      root?.removeEventListener("focusout", onOut);
      window.removeEventListener("bubbles:boop", onBoop);
      window.removeEventListener("bubbles:spark", onSpark);
      window.removeEventListener("pointerdown", onActivity);
      window.removeEventListener("keydown", onActivity);
      story.excite = 0;
    };
  }, []);

  return (
    <div ref={wrap} className="cw-bubbles" data-show="0">
      <button
        type="button"
        className="cw-bubbles-hit"
        aria-label="Say hi to Bubbles"
        onClick={() => {
          if (performance.now() - boopAt.current < 900) return;
          boopAt.current = performance.now();
          story.boops += 1;
          window.dispatchEvent(new CustomEvent("bubbles:boop", { detail: story.boops }));
        }}
        onPointerEnter={() => {
          hovered.current = true;
        }}
        onPointerLeave={() => {
          hovered.current = false;
        }}
      />
      <div ref={figure} className="cw-bubbles-figure">
        <BubblesFigure uid="host" />
        <div ref={sparks} className="cw-sparks" aria-hidden="true">
          {SPARKS.map((s, k) => (
            <span key={k} style={{ "--dx": `${s.dx}px`, "--dy": `${s.dy}px`, "--r": `${s.r}deg`, "--d": `${s.d}ms` } as Vars}>
              {s.heart ? (
                <svg viewBox="-10 -5 20 17" width="12" height="11" focusable="false">
                  <path d="M0 0c-2-4-9-3-9 2 0 4 6 7 9 9 3-2 9-5 9-9 0-5-7-6-9-2Z" fill="#FF5FA8" />
                </svg>
              ) : null}
            </span>
          ))}
        </div>
      </div>
      <BubbleLocket />
      <div className="cw-zzz" aria-hidden="true">
        <span>z</span>
        <span>z</span>
        <span>z</span>
      </div>
    </div>
  );
}
