import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { InsightsClient } from "./InsightsClient";

export const metadata: Metadata = {
  title: "Patterns | Bubbles",
  description: "Patterns from your own logs in plain words, with how confident Bubbles is and why.",
};

export default function InsightsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <InsightsClient />
      </ApiProvider>
    </AuthProvider>
  );
}