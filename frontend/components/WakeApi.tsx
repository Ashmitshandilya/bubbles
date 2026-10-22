"use client";

import { useEffect } from "react";
import { wakeUrl } from "../app/lib/wake-api";

/**
 * The free API host sleeps after a quiet spell and takes up to a minute to start. The landing and sign-in pages do not talk to it,
 * so without this the wait only began after sign-in. One quiet /health call on arrival lets it start while the person reads or types.
 */
export function WakeApi() {
  useEffect(() => {
    const url = wakeUrl(window.location.protocol, window.location.origin, process.env.NEXT_PUBLIC_BUBBLES_NATIVE === "1");
    if (!url) return;
    try {
      if (window.sessionStorage.getItem("bubbles-woke") === "1") return;
      window.sessionStorage.setItem("bubbles-woke", "1");
    } catch {
      /* storage can be blocked: wake it anyway, once per page load */
    }
    // The answer is not used. keepalive lets it finish even if the person moves on to another page straight away.
    void fetch(url, { cache: "no-store", keepalive: true }).catch(() => { /* a failed wake is the same as no wake */ });
  }, []);
  return null;
}
