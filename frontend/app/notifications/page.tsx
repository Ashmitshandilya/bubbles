import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { NotificationsClient } from "./NotificationsClient";

export const metadata: Metadata = {
  title: "Notifications | Bubbles",
  description: "Your gentle reminders in one place.",
};

export default function NotificationsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <NotificationsClient />
      </ApiProvider>
    </AuthProvider>
  );
}
