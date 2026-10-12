"use client";

// The Android app's link to the phone: splash screen, back button, printing and session refresh. app/layout.tsx mounts
// it only in the app build. Capacitor and Supabase are loaded with import(), not a static import: Next ships every
// client module a layout imports in that layout's chunk on every website page (and runs it), rendered or not, and the
// website must never download or run Capacitor.

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import type { PluginListenerHandle } from "@capacitor/core";

/** The app's own plugin (android/.../PrintPlugin.java): the system print dialog, which also offers Save as PDF. */
type BubblesPrint = { print(options: { title?: string }): Promise<void> };

function hideSplash() {
  void import("@capacitor/splash-screen").then(({ SplashScreen }) => SplashScreen.hide()).catch(() => undefined);
}

/** Android back: close the top sheet or popover, else go back a screen, else (first screen) minimise. */
async function goBack(canGoBack: boolean, minimize: () => Promise<void>) {
  // Every sheet is a native modal <dialog>: do what Escape does. A sheet may refuse the "cancel" (the tracker log
  // sheet does while saving); the press is still used up, as Escape's would be.
  const dialogs = document.querySelectorAll<HTMLDialogElement>("dialog[open]");
  const dialog = dialogs[dialogs.length - 1];
  if (dialog) {
    if (dialog.dispatchEvent(new Event("cancel", { cancelable: true }))) dialog.close();
    return;
  }
  // A popover that is not a <dialog> (the notification list) renders role="dialog" only while open and closes on
  // Escape. The press counts as handled only if that element is gone afterwards: React commits an update made during
  // a keydown in a microtask, so it has re-rendered before the next task. Otherwise back goes on as usual.
  const popover = document.querySelector('[role="dialog"]:not(dialog)');
  if (popover) {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    if (!popover.isConnected) return;
  }
  // Android's convention for the first screen: minimise and keep the app's state, never exit.
  if (canGoBack) window.history.back();
  else await minimize();
}

export function NativeBridge() {
  const pathname = usePathname();
  const splashHidden = useRef(false);

  // In the app "/" is only NativeEntry's redirect, so the first other path is the first real screen.
  useEffect(() => {
    if (pathname === "/" || splashHidden.current) return;
    splashHidden.current = true;
    hideSplash();
  }, [pathname]);

  useEffect(() => {
    // The splash must never stick, even if the first screen fails to route.
    const splashTimer = window.setTimeout(hideSplash, 5000);
    const webPrint = window.print;
    const handles: PluginListenerHandle[] = [];
    let active = true;

    void (async () => {
      const [{ App }, { registerPlugin }, { supabase }] = await Promise.all([
        import("@capacitor/app"),
        import("@capacitor/core"),
        import("../lib/supabase"),
      ]);
      if (!active) return;
      // window.print() does nothing in an Android web view. The print buttons only call it (no return value, no
      // print events), so routing it to the plugin is enough.
      const printer = registerPlugin<BubblesPrint>("BubblesPrint");
      window.print = () => void printer.print({ title: document.title }).catch(() => undefined);
      const listeners = await Promise.all([
        App.addListener("backButton", ({ canGoBack }) => void goBack(canGoBack, () => App.minimizeApp())),
        // supabase-js cannot tell when an app is in the background, so refresh the session only while it is in front.
        App.addListener("appStateChange", ({ isActive }) => {
          void (isActive ? supabase.auth.startAutoRefresh() : supabase.auth.stopAutoRefresh());
        }),
      ]);
      if (active) handles.push(...listeners);
      else listeners.forEach((listener) => void listener.remove());
    })();

    return () => {
      active = false;
      window.clearTimeout(splashTimer);
      window.print = webPrint;
      handles.forEach((handle) => void handle.remove());
    };
  }, []);

  return null;
}
