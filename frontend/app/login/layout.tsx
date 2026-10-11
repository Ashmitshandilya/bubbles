import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign in | Bubbles",
  description: "Sign in or create your Bubbles account. Bubbles is a health companion that remembers your story and does not diagnose.",
  alternates: { canonical: "/login" },
};

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}
