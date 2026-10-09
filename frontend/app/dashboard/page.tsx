import type { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { DashboardClient } from "./dashboard/DashboardClient";

export const metadata: Metadata = {
  title: "Today | Bubbles",
  description: "What matters today, your signals this week, and what's coming up, from your own logs.",
};

export default function DashboardPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <DashboardClient />
      </ApiProvider>
    </AuthProvider>
  );
}