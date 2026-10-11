import type { Metadata } from "next";
import { Landing } from "./landing/Landing";

export const metadata: Metadata = {
  title: "Bubbles | your personal health companion",
  description:
    "Bubbles remembers your health so you don't have to. Talk to Bubbles, connect your cycle, sleep, mood and symptoms, and understand what matters today.",
  alternates: { canonical: "/" },
};

export default function HomePage() {
  return <Landing />;
}
