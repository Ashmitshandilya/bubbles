"use client";

import { useEffect } from "react";
import Lenis from "lenis";

/**
 * Smooth, inertial scrolling for the landing page only. Why: it makes the pinned showcase and the word-by-word statement feel
 * continuous. It is skipped entirely for people who ask for reduced motion, and touch devices keep their native scrolling.
 * Also marks the page as "js on" so reveal animations only hide content once scripts are running.
 */
export function SmoothScroll() {
  useEffect(() => {
    const root = document.querySelector<HTMLElement>(".lp");
    root?.setAttribute("data-js", "true");
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return () => root?.removeAttribute("data-js");

    const lenis = new Lenis({ lerp: 0.11 });
    let raf = 0;
    const loop = (time: number) => {
      lenis.raf(time);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    const onClick = (event: MouseEvent) => {
      const link = (event.target as HTMLElement).closest<HTMLAnchorElement>('a[href^="#"]');
      const id = link?.getAttribute("href")?.slice(1);
      const target = id ? document.getElementById(id) : null;
      if (!target) return;
      event.preventDefault();
      lenis.scrollTo(target, { offset: -72 });
    };
    document.addEventListener("click", onClick);

    return () => {
      document.removeEventListener("click", onClick);
      cancelAnimationFrame(raf);
      lenis.destroy();
      root?.removeAttribute("data-js");
    };
  }, []);
  return null;
}
