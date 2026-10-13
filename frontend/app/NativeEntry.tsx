"use client";

// The Android app's "/" (the website shows the marketing page there). Signed-in people go straight on to the first real
// screen; signed-out people get the welcome screen (app/NativeWelcome.tsx, rendered on the server and passed in).

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

const FIRST_SCREEN = "/dashboard";

/** `?to=` is followed only to a path on this origin; anything else (another host, "//x", "/\x", a scheme) goes home. */
export function entryTarget(to: string | null, origin: string): string {
  if (!to || !to.startsWith("/") || to.startsWith("//") || to.startsWith("/\\")) return FIRST_SCREEN;
  try {
    // Check what the URL parser makes of it, not just the prefix: it drops tabs and newlines, so "/\t/x.example" is "//x.example".
    const url = new URL(to, origin);
    // "/" would only land back here.
    if (url.origin !== origin || url.pathname === "/") return FIRST_SCREEN;
    return url.pathname + url.search + url.hash;
  } catch {
    return FIRST_SCREEN;
  }
}

/** Where "/" goes: a `?to=` path (its own page checks sign-in), else the first screen when signed in, else null (the welcome). */
export function entryRoute(to: string | null, origin: string, signedIn: boolean): string | null {
  if (to !== null) return entryTarget(to, origin);
  return signedIn ? FIRST_SCREEN : null;
}

// Set once "/" has routed. Arriving here again means Android back from the first screen after signing in (the welcome
// stays under it in history), which minimises the app as on any first screen.
let routed = false;

export function NativeEntry({ welcome, children }: { welcome: ReactNode; children?: ReactNode }) {
  const router = useRouter();
  const [showWelcome, setShowWelcome] = useState(false);

  useEffect(() => {
    const { pathname, search, hash, origin } = window.location;
    if (pathname !== "/") {
      // The app's file server answers a full page load at any deeper path with this "/" document. Its React tree belongs
      // to "/", and hydrating it at another address seeds the router cache with the wrong tree, so reload at "/" first.
      window.location.replace(`/?to=${encodeURIComponent(pathname + search + hash)}`);
      return;
    }
    let active = true;
    // Loaded on demand so the website's "/", which also ships this module, never downloads it for nothing.
    void import("../lib/supabase")
      .then(async ({ isSupabaseConfigured, supabase }) => isSupabaseConfigured && Boolean((await supabase.auth.getSession()).data.session))
      .catch(() => false)
      .then((signedIn) => {
        if (!active) return;
        const target = entryRoute(new URLSearchParams(search).get("to"), origin, signedIn);
        const returning = routed;
        routed = true;
        if (target === null) {
          setShowWelcome(true);
          return;
        }
        // replace, not push: back from the first screen then minimises the app instead of returning to this redirect.
        router.replace(target);
        if (returning) void import("@capacitor/app").then(({ App }) => App.minimizeApp()).catch(() => undefined);
      });
    return () => {
      active = false;
    };
  }, [router]);

  if (showWelcome) return welcome;
  return (
    <main className="nw-opening flex min-h-dvh flex-1 flex-col items-center justify-center gap-5">
      {children}
      <p role="status" className="m-0 flex items-center gap-3 text-body font-bold text-ink-soft">
        Opening Bubbles
        <span className="flex gap-1.5" aria-hidden="true">
          <span className="bubbles-thinking-dot" />
          <span className="bubbles-thinking-dot" />
          <span className="bubbles-thinking-dot" />
        </span>
      </p>
    </main>
  );
}
