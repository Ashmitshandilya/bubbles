import type { Metadata } from "next";
import { PartnerClient } from "./PartnerClient";
import { isNativeApp } from "../../../../lib/native";

// A shared link carries a secret in its path: keep it out of search results and out of Referer headers.
export const metadata: Metadata = {
  title: "Shared cycle estimate | Bubbles",
  description: "A private cycle estimate someone chose to share with you through Bubbles.",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

// Shared links open on the website, never in the Android app, but its static export needs every dynamic route
// to list its params: one placeholder satisfies it. Undefined on the website, so this route stays fully dynamic.
export const generateStaticParams = isNativeApp ? async () => [{ token: "_" }] : undefined;

export default async function PartnerPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <PartnerClient token={token} />;
}
