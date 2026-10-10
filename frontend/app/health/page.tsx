import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { HealthClient } from "./HealthClient";

export const metadata: Metadata = {
  title: "My health | Bubbles",
  description: "Everything you log in one place: trackers, your logging so far, and body systems without diagnoses.",
};

export default function HealthPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <HealthClient />
      </ApiProvider>
    </AuthProvider>
  );
}