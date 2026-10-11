import type { Metadata } from "next";

// The page that finishes an email sign-in link: never indexed, never shared.
export const metadata: Metadata = {
  title: "Signing you in | Bubbles",
  description: "Finishing your Bubbles sign-in.",
  robots: { index: false, follow: false },
};

export default function CallbackLayout({ children }: { children: React.ReactNode }) {
  return children;
}
