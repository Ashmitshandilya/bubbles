"use client";

import { useRef, useState, type ReactNode } from "react";
import { useMotionValueEvent, useReducedMotion, useScroll } from "motion/react";
import { ChatPreview, CyclePreview, PartnerPreview, PatternsPreview } from "./previews";

type Feature = { id: string; title: string; body: string; preview: ReactNode };

const FEATURES: Feature[] = [
  {
    id: "talk",
    title: "Talk it through",
    body: "Say how you feel in English, Hindi or Hinglish. Bubbles replies with sources you can open and says when it is unsure.",
    preview: <ChatPreview />,
  },
  {
    id: "patterns",
    title: "See your patterns",
    body: "Sleep, mood, activity and cycle are logged side by side. A link shows up only when it is clear and repeated.",
    preview: <PatternsPreview />,
  },
  {
    id: "cycle",
    title: "Know your cycle",
    body: "Estimates come with honest ranges, gentle tips and a log that takes ten seconds.",
    preview: <CyclePreview />,
  },
  {
    id: "share",
    title: "Share with someone you trust",
    body: "Choose exactly what one person can see. Stop sharing at any moment.",
    preview: <PartnerPreview />,
  },
];

/**
 * Pinned on desktop: the section is four screens tall and the frame stays put while the scroll position picks the feature.
 * That order of reveal is the story (say it, see it, track it, share it). On phones it is simply four stacked blocks.
 */
export function Showcase() {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLElement>(null);
  const [active, setActive] = useState(0);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });

  useMotionValueEvent(scrollYProgress, "change", (v) => {
    const next = Math.min(FEATURES.length - 1, Math.max(0, Math.floor(v * FEATURES.length)));
    setActive((prev) => (prev === next ? prev : next));
  });

  const jump = (i: number) => {
    const el = ref.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY;
    const travel = el.offsetHeight - window.innerHeight;
    window.scrollTo({ top: top + ((i + 0.08) / FEATURES.length) * travel, behavior: reduce ? "auto" : "smooth" });
  };

  return (
    <section ref={ref} id="how" className="lp-show" aria-labelledby="lp-show-h">
      <div className="lp-show__stick lp-wrap">
        <div>
          <div className="lp-show__title">
            <h2 id="lp-show-h">One place for the whole picture</h2>
          </div>
          <div className="lp-show__nav" role="group" aria-label="Features">
            {FEATURES.map((f, i) => (
              <button key={f.id} type="button" className="lp-show__btn" aria-current={i === active} onClick={() => jump(i)}>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </button>
            ))}
          </div>
        </div>
        <div className="lp-show__frame">
          {FEATURES.map((f, i) => (
            <article key={f.id} className="lp-feat" data-active={i === active}>
              <div className="lp-feat__head">
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </div>
              {f.preview}
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
