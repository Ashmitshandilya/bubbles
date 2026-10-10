"use client";

import Image from "next/image";
import { useRef, type PointerEvent } from "react";
import { motion, useMotionValue, useReducedMotion, useScroll, useSpring, useTransform } from "motion/react";
import { ArrowDown } from "@phosphor-icons/react";
import { AuthCta } from "./AuthCta";
import { SoapBubbles } from "./SoapBubbles";

/**
 * Asymmetric split hero. Motion has one job here: depth. The portrait drifts and tilts a few degrees toward the pointer
 * and rises slightly as you scroll away, so the figure feels like an object in front of the page, not a flat picture.
 */
export function Hero() {
  const reduce = useReducedMotion();
  const section = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: section, offset: ["start start", "end start"] });
  const lift = useTransform(scrollYProgress, [0, 1], [0, reduce ? 0 : -70]);
  const zoom = useTransform(scrollYProgress, [0, 1], [1, reduce ? 1 : 1.07]);

  const px = useMotionValue(0);
  const py = useMotionValue(0);
  const sx = useSpring(px, { stiffness: 110, damping: 18 });
  const sy = useSpring(py, { stiffness: 110, damping: 18 });
  const rotateY = useTransform(sx, [-1, 1], [reduce ? 0 : -5, reduce ? 0 : 5]);
  const rotateX = useTransform(sy, [-1, 1], [reduce ? 0 : 4, reduce ? 0 : -4]);

  const onMove = (event: PointerEvent<HTMLDivElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    px.set(((event.clientX - box.left) / box.width) * 2 - 1);
    py.set(((event.clientY - box.top) / box.height) * 2 - 1);
  };
  const onLeave = () => {
    px.set(0);
    py.set(0);
  };

  // Entrance is plain CSS (see .lp-rise) so the headline and portrait paint without waiting for JavaScript.
  return (
    <section ref={section} className="lp-hero" aria-labelledby="lp-h1">
      <div className="lp-wrap lp-hero__grid">
        <div className="lp-hero__copy">
          <h1 id="lp-h1" className="lp-rise" style={{ ["--d" as string]: "0.05s" }}>
            Your body keeps a story.
            <em>Bubbles remembers it.</em>
          </h1>
          <p className="lp-hero__sub lp-rise" style={{ ["--d" as string]: "0.16s" }}>
            A health companion that listens, remembers and connects your sleep, mood, cycle and symptoms over time.
          </p>
          <div className="lp-hero__cta lp-rise" style={{ ["--d" as string]: "0.26s" }}>
            <AuthCta />
            <a href="#how" className="lp-btn lp-btn--quiet">
              See how it works
              <ArrowDown size={18} weight="bold" aria-hidden="true" />
            </a>
          </div>
        </div>

        <div className="lp-stage lp-pop" onPointerMove={onMove} onPointerLeave={onLeave}>
          <div className="lp-stage__glow" aria-hidden="true" />
          <SoapBubbles />
          <motion.div className="lp-arch" style={{ y: lift, scale: zoom, rotateX, rotateY, transformPerspective: 1100 }}>
            <Image
              src="/brand/bubbles-hero.jpg"
              alt="Bubbles, a white unicorn doctor with a pastel pink and lilac mane, a nurse cap and a stethoscope"
              fill
              priority
              sizes="(min-width: 960px) 36vw, 90vw"
            />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
