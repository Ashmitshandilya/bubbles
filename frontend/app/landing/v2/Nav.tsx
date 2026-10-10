"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { BubblesMark } from "../BubblesMark";
import { AuthCta } from "./AuthCta";

/** Floating pill. It softens until you scroll; a sentinel at the top tells it when, so there is no scroll listener. */
export function Nav() {
  const sentinel = useRef<HTMLDivElement>(null);
  const [stuck, setStuck] = useState(false);

  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setStuck(!entry.isIntersecting));
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <>
      <div ref={sentinel} className="lp-nav-sentinel" aria-hidden="true" />
      <header className="lp-nav" data-stuck={stuck}>
        <Link href="/" className="lp-brand" aria-label="Bubbles home">
          <BubblesMark size={34} />
          Bubbles
        </Link>
        <nav className="lp-nav__links" aria-label="Sections">
          <a href="#how">How it works</a>
          <a href="#safety">Safety</a>
          <a href="#faq">Questions</a>
        </nav>
        <div className="lp-nav__cta">
          <Link href="/login" className="lp-btn lp-btn--quiet lp-btn--sm lp-nav__signin">
            Sign in
          </Link>
          <AuthCta size="sm" />
        </div>
      </header>
    </>
  );
}
