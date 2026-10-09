import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { MoodClient } from "./MoodClient";

export const metadata: Metadata = {
  title: "Mood Tracking | Bubbles",
  description: "Emotional state, stress, and wellbeing.",
};

export default function MoodPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <MoodClient />
      </ApiProvider>
    </AuthProvider>
  );
}
