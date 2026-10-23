import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { CompanionClient } from "../../companion/CompanionClient";

export const metadata: Metadata = {
  title: "Heart-to-heart | Bubbles",
  description: "Talk through what is on your heart.",
  robots: { index: false },
};

export default function HeartToHeartPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <CompanionClient mode="orbit" />
      </ApiProvider>
    </AuthProvider>
  );
}
