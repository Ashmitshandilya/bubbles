import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { CompanionClient } from "./CompanionClient";

export const metadata: Metadata = {
  title: "Companion | Bubbles",
  description: "Talk to Bubbles, your health companion with context, memory, and intelligent suggestions.",
};

export default function CompanionPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <CompanionClient />
      </ApiProvider>
    </AuthProvider>
  );
}
