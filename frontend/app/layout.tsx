import type { Metadata, Viewport } from "next";
import { Fredoka, Nunito } from "next/font/google";
import "./globals.css";
import { PrivacyVeilProvider } from "../components/PrivacyVeil";
import { AuthLinkRedirect } from "../components/AuthLinkRedirect";
import { PrivacyNotice } from "../components/PrivacyNotice";
import { NativeBridge } from "../components/NativeBridge";
import { isNativeApp } from "../lib/native";

// Self-hosted by next/font (no runtime request to Google) with size-adjusted
// fallback metrics, so text does not jump when the web fonts arrive.
const nunito = Nunito({
  subsets: ["latin"],
  variable: "--font-nunito",
  display: "swap",
});

const fredoka = Fredoka({
  subsets: ["latin"],
  variable: "--font-fredoka",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Bubbles | Your personal health companion",
  description:
    "Bubbles remembers your health so you don't have to. Talk to Bubbles, connect your cycle, sleep, mood and symptoms, and understand what matters today.",
  // The public address of the site (set NEXT_PUBLIC_SITE_URL in the host; falls back to the production domain).
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://heybubbles.in"),
  applicationName: "Bubbles",
  openGraph: {
    title: "Bubbles | Your personal health companion",
    description: "A health companion that listens, remembers and connects the dots over time. It does not diagnose.",
    type: "website",
    siteName: "Bubbles",
    locale: "en_IN",
  },
  // The share picture itself comes from app/opengraph-image.tsx and app/twitter-image.tsx.
  twitter: {
    card: "summary_large_image",
    title: "Bubbles | Your personal health companion",
    description: "A health companion that listens, remembers and connects the dots over time. It does not diagnose.",
  },
  // Stays out of search engines until you deliberately launch: set NEXT_PUBLIC_ALLOW_INDEXING=true on the host.
  robots: process.env.NEXT_PUBLIC_ALLOW_INDEXING === "true" ? "index, follow" : "noindex, nofollow",
};

export const viewport: Viewport = {
  themeColor: "#FFF6FA",
  colorScheme: "light",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  interactiveWidget: "resizes-content",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${nunito.variable} ${fredoka.variable}`}>
      <body className="bubbles-shell min-h-dvh flex flex-col">
        <AuthLinkRedirect />
        <PrivacyVeilProvider>{children}</PrivacyVeilProvider>
        <PrivacyNotice />
        {isNativeApp && <NativeBridge />}
      </body>
    </html>
  );
}
