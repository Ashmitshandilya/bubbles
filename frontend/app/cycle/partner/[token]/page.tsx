import type { Metadata } from "next";
import { PartnerClient } from "./PartnerClient";

// A shared link carries a secret in its path: keep it out of search results and out of Referer headers.
export const metadata: Metadata = {
  title: "Shared cycle estimate | Bubbles",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function PartnerPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <PartnerClient token={token} />;
}
