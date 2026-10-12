"use client";

// The Android app's "/" (the website shows the marketing page there): it forwards to the first real screen.
// /dashboard itself sends signed-out people on to /login.

import { useEffect, type ReactNode } from "react";
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

export function NativeEntry({ children }: { children?: ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    const { pathname, search, hash, origin } = window.location;
    if (pathname !== "/") {
      // The app's file server answers a full page load at any deeper path with this "/" document. Its React tree belongs
      // to "/", and hydrating it at another address seeds the router cache with the wrong tree, so reload at "/" first.
      window.location.replace(`/?to=${encodeURIComponent(pathname + search + hash)}`);
      return;
    }
    // replace, not push: back from the first screen then minimises the app instead of returning to this redirect.
    router.replace(entryTarget(new URLSearchParams(search).get("to"), origin));
  }, [router]);

  return (
    <main className="flex min-h-dvh flex-1 flex-col items-center justify-center gap-4 bg-blush">
      {children}
      <p role="status" className="m-0 text-body font-bold text-ink-soft">
        Opening Bubbles…
      </p>
    </main>
  );
}
