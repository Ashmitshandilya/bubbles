import type { Metadata } from "next";
import { PartnerShareClient } from "./PartnerShareClient";

// A shared link carries a secret in its path: keep it out of search results and out of Referer headers.
export const metadata: Metadata = {
  title: "Shared with you | Bubbles",
  description: "A private summary someone chose to share with you through Bubbles.",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function PartnerSharePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <PartnerShareClient token={token} />;
}
