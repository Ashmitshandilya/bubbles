import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { OnboardingClient } from "./OnboardingClient";

export const metadata: Metadata = {
  title: "Set up Bubbles",
  description: "A few questions so Bubbles can fit you.",
  robots: { index: false },
};

export default function OnboardingPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <OnboardingClient />
      </ApiProvider>
    </AuthProvider>
  );
}
