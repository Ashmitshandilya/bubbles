import type { Metadata } from "next";
import { BubblesMascot } from "../components/BubblesMascot";
import { isNativeApp } from "../lib/native";
import { Landing } from "./landing/Landing";
import { NativeEntry } from "./NativeEntry";
import { NativeWelcome } from "./NativeWelcome";

export const metadata: Metadata = {
  title: "Bubbles | your personal health companion",
  description:
    "Bubbles remembers your health so you don't have to. Talk to Bubbles, connect your cycle, sleep, mood and symptoms, and understand what matters today.",
  alternates: { canonical: "/" },
};

export default function HomePage() {
  // The Android app has no marketing page: its "/" forwards signed-in people to the first real screen and shows
  // signed-out people a welcome screen. Both are rendered here, on the server, so NativeEntry's client code (which the
  // website's "/" also ships) stays tiny.
  if (isNativeApp) {
    return (
      <NativeEntry welcome={<NativeWelcome />}>
        <BubblesMascot size={88} />
      </NativeEntry>
    );
  }
  return <Landing />;
}
