"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight } from "@phosphor-icons/react";
import { isSupabaseConfigured, supabase } from "../../../lib/supabase";

/**
 * One call to action everywhere: "Start with Bubbles". Renders the signed-out version on the server and on first
 * paint (no hydration mismatch), then switches to "Open my Bubbles" when a session exists.
 */
export function AuthCta({ size = "lg", tone = "primary" }: { size?: "sm" | "lg"; tone?: "primary" | "quiet" }) {
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

  const cls = `lp-btn lp-btn--${tone} ${size === "sm" ? "lp-btn--sm" : ""}`;
  return (
    <Link href={signedIn ? "/dashboard" : "/login?mode=signup"} className={cls}>
      {signedIn ? "Open my Bubbles" : "Start with Bubbles"}
      <ArrowRight size={size === "sm" ? 16 : 18} weight="bold" aria-hidden="true" />
    </Link>
  );
}
