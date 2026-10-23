import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { UnderstandingClient } from "./UnderstandingClient";

export const metadata: Metadata = {
  title: "How Bubbles understands you | Bubbles",
  description: "What Bubbles has learned about how you like to be talked to. Correct it or clear it any time.",
};

export default function UnderstandingPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <UnderstandingClient />
      </ApiProvider>
    </AuthProvider>
  );
}
