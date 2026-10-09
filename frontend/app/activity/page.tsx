import { Metadata } from "next";
import { AuthProvider } from "../../components/Providers";
import { ApiProvider } from "../../components/Providers";
import { ActivityClient } from "./ActivityClient";

export const metadata: Metadata = {
  title: "Activity Tracking | Bubbles",
  description: "Workouts, steps, and movement data with adaptive recommendations.",
};

export default function ActivityPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <ActivityClient />
      </ApiProvider>
    </AuthProvider>
  );
}