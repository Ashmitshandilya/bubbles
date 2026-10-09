import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { HydrationClient } from "./HydrationClient";

export const metadata: Metadata = {
  title: "Hydration | Bubbles",
  description: "Water intake, your garden and gentle reminders.",
};

export default function HydrationPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <HydrationClient />
      </ApiProvider>
    </AuthProvider>
  );
}
