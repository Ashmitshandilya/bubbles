"use client";

import { useEffect, useRef } from "react";
import { WALK_STOPS, walkPoint } from "../world/rig";
import { CHAPTER_INDEX, clamp01, hopT, isLead, onStoryFrame, range, rectOf, say, story } from "./store";

/**
 * The two places where Bubbles visibly travels along a path:
 *
 * 1. Carry hop (Track to Cycle): an air route from where you confirmed your
 *    records to Bubbles' seat on the cycle ring. The three saved records lift off
 *    their rows, ride along behind Bubbles like a comet, and sink into the ring.
 * 2. Memory walk (desktop only): a footpath under the memory zoom. Bubbles walks it
 *    stone by stone (Today, Week, Season, Story); the dots light up and heart
 *    hoofprints appear only where Bubbles has been, and the whole road glows when
 *    Bubbles looks back.
 *
 * Everything is one fixed, decorative SVG updated from the story frame loop.
 */

const STONE_LABELS = ["Today", "Week", "Season", "Story"];
const PRINTS = 12;
const HEART = "M0 0c-2-4-9-3-9 2 0 4 6 7 9 9 3-2 9-5 9-9 0-5-7-6-9-2Z";
const ROAD_FROM = -0.06;
const ROAD_TO = 1.06;
const ROAD_SAMPLES = 64;

const f1 = (v: number) => v.toFixed(1);

export function TravelRoutes() {
  const hopGroup = useRef<SVGGElement>(null);
  const ahead = useRef<SVGPathElement>(null);
  const glow = useRef<SVGPathElement>(null);
  const core = useRef<SVGPathElement>(null);
  const riders = useRef<Array<SVGCircleElement | null>>([]);
  const ripple = useRef<SVGEllipseElement>(null);

  const walkGroup = useRef<SVGGElement>(null);
  const walkAhead = useRef<SVGPathElement>(null);
  const walkLit = useRef<SVGPathElement>(null);
  const walkGlow = useRef<SVGPathElement>(null);
  const walkClip = useRef<SVGRectElement>(null);
  const walkGrad = useRef<SVGLinearGradientElement>(null);
  const prints = useRef<Array<SVGGElement | null>>([]);
  const stones = useRef<Array<SVGGElement | null>>([]);

  useEffect(() => {
    const track = CHAPTER_INDEX.track;
    const remember = CHAPTER_INDEX.remember;
    const hop = story.hop;
    let hopShown = false;
    let lastH = 0;
    let ownsFocus = false;
    let rowCache: Array<{ x: number; y: number }> = [];

    let walkShown = false;
    let built = { vw: 0, vh: 0, dy: -1 };
    const printOn: boolean[] = Array(PRINTS).fill(false);
    const stoneOn: boolean[] = Array(WALK_STOPS.length).fill(false);
    let lastRememberP = 0;
    let lookedBack = false;

    /** Point on the hop route at u (0..1), interpolated between samples. */
    const hopAt = (u: number) => {
      const n = hop.n - 1;
      const f = Math.min(n, Math.max(0, u * n));
      const i = Math.min(n - 1, Math.floor(f));
      const t = f - i;
      return {
        x: hop.pts[i * 2] + (hop.pts[(i + 1) * 2] - hop.pts[i * 2]) * t,
        y: hop.pts[i * 2 + 1] + (hop.pts[(i + 1) * 2 + 1] - hop.pts[i * 2 + 1]) * t,
      };
    };
    const hopPath = (u0: number, u1: number) => {
      if (u1 - u0 < 0.002) return "";
      const n = hop.n - 1;
      const a = hopAt(u0);
      let d = `M${f1(a.x)} ${f1(a.y)}`;
      for (let k = Math.ceil(u0 * n + 1e-6); k < u1 * n; k += 1) d += `L${f1(hop.pts[k * 2])} ${f1(hop.pts[k * 2 + 1])}`;
      const b = hopAt(u1);
      return `${d}L${f1(b.x)} ${f1(b.y)}`;
    };

    /** Screen y (px, before the group offset) of the road at u. */
    const roadY = (u: number) => ((1 - walkPoint(clamp01(u)).y) / 2) * story.vh + story.bubbles.feet.dy;
    const roadX = (u: number) => ((walkPoint(u).x + 1) / 2) * story.vw;

    const buildWalk = () => {
      const pts: Array<[number, number]> = [];
      for (let k = 0; k <= ROAD_SAMPLES; k += 1) {
        const u = ROAD_FROM + ((ROAD_TO - ROAD_FROM) * k) / ROAD_SAMPLES;
        pts.push([roadX(u), roadY(u)]);
      }
      // Catmull-Rom through the samples, as cubic Béziers.
      let d = `M${f1(pts[0][0])} ${f1(pts[0][1])}`;
      for (let k = 0; k < pts.length - 1; k += 1) {
        const p0 = pts[Math.max(0, k - 1)];
        const p1 = pts[k];
        const p2 = pts[k + 1];
        const p3 = pts[Math.min(pts.length - 1, k + 2)];
        d += `C${f1(p1[0] + (p2[0] - p0[0]) / 6)} ${f1(p1[1] + (p2[1] - p0[1]) / 6)} ${f1(p2[0] - (p3[0] - p1[0]) / 6)} ${f1(p2[1] - (p3[1] - p1[1]) / 6)} ${f1(p2[0])} ${f1(p2[1])}`;
      }
      for (const el of [walkAhead.current, walkLit.current, walkGlow.current]) el?.setAttribute("d", d);
      const grad = walkGrad.current;
      if (grad) {
        grad.setAttribute("x1", f1(roadX(0)));
        grad.setAttribute("x2", f1(roadX(1)));
      }
      // Heart hoofprints, alternating either side of the line, turned to the road.
      prints.current.forEach((g, k) => {
        if (!g) return;
        const u = (k + 0.5) / PRINTS;
        const x = roadX(u);
        const y = roadY(u);
        const ang = Math.atan2(roadY(u + 0.01) - y, roadX(u + 0.01) - x);
        const off = k % 2 ? 4 : -4;
        const ox = -Math.sin(ang) * off;
        const oy = Math.cos(ang) * off;
        g.setAttribute("transform", `translate(${f1(x + ox)} ${f1(y + oy)}) rotate(${((ang * 180) / Math.PI + 90).toFixed(1)}) scale(0.62)`);
      });
      stones.current.forEach((g, k) => {
        if (!g) return;
        const u = WALK_STOPS[k];
        g.setAttribute("transform", `translate(${f1(roadX(u))} ${f1(roadY(u))})`);
      });
      built = { vw: story.vw, vh: story.vh, dy: story.bubbles.feet.dy };
    };

    return onStoryFrame(() => {
      if (!story.active) return;

      /* ── Carry hop ─────────────────────────────────────────── */
      const g = hopGroup.current;
      const trackP = story.chapters[track].p;
      const h = hopT();
      const hopOn = hop.live && (story.current === track || (story.current === track - 1 && story.blend > 0.9));
      if (g && hopOn !== hopShown) {
        g.dataset.show = hopOn ? "1" : "0";
        hopShown = hopOn;
      }
      if (g && hopOn) {
        const head = h > 0 ? hop.head : 0;
        ahead.current?.setAttribute("d", hopPath(head, 1));
        ahead.current?.style.setProperty("opacity", (range(trackP, 0.88, 0.96) * 0.6 * (1 - range(h, 0.9, 1))).toFixed(3));
        const tail0 = Math.max(0, head - 0.3);
        const tailU = tail0 + (head - tail0) * range(h, 0.85, 1);
        const trail = h > 0.01 ? hopPath(tailU, head) : "";
        glow.current?.setAttribute("d", trail);
        core.current?.setAttribute("d", trail);

        // Riders: the three confirmed records, from their rows to Bubbles' hooves, then along the route.
        if (h === 0 && trackP > 0.86) {
          const rows = document.querySelectorAll<HTMLElement>(".cw-ch--track .cw-records li");
          rowCache = Array.from(rows, (row) => {
            const r = rectOf(row);
            return { x: r.left, y: r.top + r.height / 2 };
          });
        }
        riders.current.forEach((c, k) => {
          if (!c) return;
          let x = 0;
          let y = 0;
          let o = 0;
          if (h === 0) {
            const r = range(trackP, 0.88 + 0.02 * k, 0.95 + 0.02 * k);
            const from = rowCache[k];
            if (from && r > 0) {
              const to = story.bubbles.feet;
              const mx = (from.x + to.x) / 2;
              const my = Math.min(from.y, to.y) - 40;
              const a = (1 - r) * (1 - r);
              const b = 2 * (1 - r) * r;
              const cc = r * r;
              x = a * from.x + b * mx + cc * to.x;
              y = a * from.y + b * my + cc * to.y;
              o = Math.min(1, r * 4);
            }
          } else {
            const pt = hopAt(Math.max(0, hop.head - 0.05 * (k + 1)));
            x = pt.x;
            y = pt.y;
            o = 1 - range(h, 0.9, 1);
          }
          c.setAttribute("cx", f1(x));
          c.setAttribute("cy", f1(y));
          c.style.opacity = o.toFixed(3);
        });

        // Bubbles eyes the destination before leaping.
        if (isLead(track) && trackP >= 0.9 && h < 0.5) {
          const nx = (hop.dest.x / story.vw) * 2 - 1;
          const ny = -((hop.dest.y / story.vh) * 2 - 1);
          story.focus = { x: nx, y: ny, side: hop.dest.x >= story.bubbles.x ? 1 : -1 };
          ownsFocus = true;
        } else if (ownsFocus) {
          ownsFocus = false;
        }

        // Landing ripple, forward only.
        if (lastH > 0 && lastH < 0.96 && h >= 0.96 && ripple.current) {
          const e = ripple.current;
          e.setAttribute("cx", f1(hop.dest.x));
          e.setAttribute("cy", f1(hop.dest.y + story.bubbles.feet.dy));
          e.animate(
            [
              { transform: "scale(0.3)", opacity: 0.8 },
              { transform: "scale(1.4)", opacity: 0 },
            ],
            { duration: 650, easing: "cubic-bezier(0.2, 0.7, 0.3, 1)" },
          );
        }
      }
      lastH = h;

      /* ── Memory walk (desktop) ─────────────────────────────── */
      const wg = walkGroup.current;
      const rem = story.chapters[remember];
      const walkOn = !story.mobile && rem.enter > 0 && rem.exit < 1;
      if (wg && walkOn !== walkShown) {
        wg.dataset.show = walkOn ? "1" : "0";
        walkShown = walkOn;
        if (!walkOn) wg.style.opacity = "0";
      }
      if (wg && walkOn) {
        if (built.vw !== story.vw || built.vh !== story.vh || Math.abs(built.dy - story.bubbles.feet.dy) > 1) buildWalk();
        const feet = story.bubbles.feet;
        const uLive = clamp01(((feet.x / story.vw) * 2 - 1 + 0.62) / 0.92);
        wg.style.opacity = (rem.enter * (1 - rem.exit)).toFixed(3);
        wg.style.transform = `translate3d(0, ${f1(feet.y - roadY(uLive))}px, 0)`;
        wg.style.setProperty("--look", range(rem.p, 0.86, 0.92).toFixed(3));
        walkClip.current?.setAttribute("width", f1(Math.max(0, feet.x)));
        prints.current.forEach((pg, k) => {
          const on = uLive > (k + 0.5) / PRINTS;
          if (pg && on !== printOn[k]) {
            printOn[k] = on;
            pg.toggleAttribute("data-on", on);
          }
        });
        stones.current.forEach((sg, k) => {
          const on = uLive >= WALK_STOPS[k] - 0.01;
          if (sg && on !== stoneOn[k]) {
            stoneOn[k] = on;
            sg.toggleAttribute("data-reached", on);
          }
        });
        if (!lookedBack && lastRememberP < 0.86 && rem.p >= 0.86) {
          lookedBack = true;
          say("Look how far we've come.", 2600);
        }
      }
      lastRememberP = rem.p;
    });
  }, []);

  return (
    <svg className="cw-route" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="cw-walk-grad" ref={walkGrad} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="1000" y2="0">
          <stop offset="0" stopColor="#FF8FBE" />
          <stop offset="0.34" stopColor="#CDBBFF" />
          <stop offset="0.67" stopColor="#FFC37A" />
          <stop offset="1" stopColor="#FF73B0" />
        </linearGradient>
        <clipPath id="cw-walk-clip" clipPathUnits="userSpaceOnUse">
          <rect ref={walkClip} x="0" y="-2000" width="0" height="6000" />
        </clipPath>
      </defs>

      <g ref={hopGroup} className="cw-hop" data-show="0">
        <path ref={ahead} className="cw-hop-ahead" />
        <path ref={glow} className="cw-hop-glow" />
        <path ref={core} className="cw-hop-core" />
        {["var(--cw-pink)", "var(--cw-lilac)", "var(--cw-sky)"].map((color, k) => (
          <circle
            key={color}
            ref={(el) => {
              riders.current[k] = el;
            }}
            className="cw-hop-rider"
            r="4"
            style={{ fill: color, opacity: 0 }}
          />
        ))}
        <ellipse ref={ripple} className="cw-hop-ripple" rx="38" ry="10" />
      </g>

      <g ref={walkGroup} className="cw-walk" data-show="0">
        <path ref={walkAhead} className="cw-walk-ahead" />
        <path ref={walkGlow} className="cw-walk-glow" clipPath="url(#cw-walk-clip)" />
        <path ref={walkLit} className="cw-walk-lit" clipPath="url(#cw-walk-clip)" />
        {Array.from({ length: PRINTS }, (_, k) => (
          <g
            key={`p${k}`}
            ref={(el) => {
              prints.current[k] = el;
            }}
            className="cw-print"
          >
            <path d={HEART} />
          </g>
        ))}
        {STONE_LABELS.map((label, k) => (
          <g
            key={label}
            ref={(el) => {
              stones.current[k] = el;
            }}
            className="cw-stone"
          >
            <circle className="cw-stone-pulse" r="5" />
            <circle className="cw-stone-dot" r="5" />
            <text y="22">{label}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}
