"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { isSupabaseConfigured, supabase } from "../../lib/supabase";

/**
 * Auth-aware call to action. Renders the signed-out version on the server and
 * on first paint (no hydration mismatch), then switches to "Open my Bubbles" when
 * a session exists.
 */
export function AuthCta({ variant }: { variant: "nav" | "hero" | "final" }) {
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    if (!isSupabaseConfigured) return;
    let active = true;
    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (active) setSignedIn(Boolean(data.session));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const size = variant === "nav" ? "cw-btn--sm" : "cw-btn--lg";

  if (signedIn) {
    return (
      <div className={`cw-cta cw-cta--${variant}`}>
        <Link href="/dashboard" className={`cw-btn cw-btn--primary ${size}`}>
          Open my Bubbles
          <ArrowIcon />
        </Link>
      </div>
    );
  }

  return (
    <div className={`cw-cta cw-cta--${variant}`}>
      {variant !== "hero" && (
        <Link href="/login" className={`cw-btn cw-btn--ghost ${size}`}>
          Sign in
        </Link>
      )}
      <Link href="/login?mode=signup" className={`cw-btn cw-btn--primary ${size}`}>
        Start with Bubbles
        <ArrowIcon />
      </Link>
    </div>
  );
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}
