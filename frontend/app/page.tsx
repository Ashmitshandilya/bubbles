import type { Metadata } from "next";
import { BubblesMascot } from "../components/BubblesMascot";
import { isNativeApp } from "../lib/native";
import { Landing } from "./landing/Landing";
import { NativeEntry } from "./NativeEntry";

export const metadata: Metadata = {
  title: "Bubbles | your personal health companion",
  description:
    "Bubbles remembers your health so you don't have to. Talk to Bubbles, connect your cycle, sleep, mood and symptoms, and understand what matters today.",
  alternates: { canonical: "/" },
};

export default function HomePage() {
  // The Android app has no marketing page: its "/" only forwards to the first real screen. The mascot is rendered
  // here, on the server, so NativeEntry's client code (which the website's "/" also ships) stays tiny.
  if (isNativeApp) {
    return (
      <NativeEntry>
        <BubblesMascot size={80} />
      </NativeEntry>
    );
  }
  return <Landing />;
}
