"use client";

import { useRef } from "react";
import { motion, useReducedMotion, useScroll, useTransform, type MotionValue } from "motion/react";

const TEXT = "Bubbles listens, remembers and connects the dots, so you walk into every appointment with the full picture.";

function Word({ word, progress, range }: { word: string; progress: MotionValue<number>; range: [number, number] }) {
  const opacity = useTransform(progress, range, [0.16, 1]);
  return (
    <motion.span className="lp-word" style={{ opacity }}>
      {word}
    </motion.span>
  );
}

/** Each word lights up as you read down the page: the sentence is the point of the product, so it is the one thing that earns a scroll effect. */
export function Statement() {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLParagraphElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.85", "end 0.5"] });
  const words = TEXT.split(" ");

  return (
    <section className="lp-statement" aria-label="What Bubbles is for">
      <div className="lp-wrap">
        {reduce ? (
          <p>{TEXT}</p>
        ) : (
          <p ref={ref} aria-label={TEXT}>
            {words.map((w, i) => (
              <Word key={`${w}-${i}`} word={w} progress={scrollYProgress} range={[i / words.length, (i + 1) / words.length]} />
            ))}
          </p>
        )}
      </div>
    </section>
  );
}
