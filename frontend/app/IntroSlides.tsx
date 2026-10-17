"use client";

// Android 2.0 welcome: three swipeable cards (scroll-snap, no library) with page dots. Swiping works by touch; the dots and
// "Next" also move it. Reduced motion: no smooth scrolling (globals.css, html[data-native] .nw2-*).

import { useEffect, useRef, useState } from "react";

export const INTRO = [
  { kicker: "Log it", title: "Say it in a sentence.", body: "\"Slept six hours, light headache.\" Bubbles turns it into a tidy log. No forms." },
  { kicker: "Remember", title: "Bubbles remembers.", body: "Sleep, mood, cycle, food, medicines. One calm place, and you decide what is saved." },
  { kicker: "Patterns", title: "See what connects.", body: "Gentle patterns over weeks, with how sure they are. Never a diagnosis." },
] as const;

export function IntroSlides() {
  const track = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(0);

  useEffect(() => {
    const el = track.current;
    if (!el) return;
    const onScroll = () => setPage(Math.round(el.scrollLeft / Math.max(1, el.clientWidth)));
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  const go = (i: number) => track.current?.scrollTo({ left: i * track.current.clientWidth });

  return (
    <section className="nw2-intro" aria-roledescription="carousel" aria-label="What Bubbles does">
      <div ref={track} className="nw2-track">
        {INTRO.map((s, i) => (
          <article key={s.kicker} className="nw2-slide" aria-roledescription="slide" aria-label={`${i + 1} of ${INTRO.length}`} aria-hidden={page !== i}>
            <p className="nw2-kicker">{s.kicker}</p>
            <h1 className="nw2-title">{s.title}</h1>
            <p className="nw2-body">{s.body}</p>
          </article>
        ))}
      </div>
      <div className="nw2-dots">
        {INTRO.map((s, i) => (
          <button key={s.kicker} type="button" aria-label={`Show card ${i + 1}`} aria-current={page === i} className="nw2-dot" onClick={() => go(i)} />
        ))}
        {page < INTRO.length - 1 && (
          <button type="button" className="nw2-next" onClick={() => go(page + 1)}>Next</button>
        )}
      </div>
    </section>
  );
}
