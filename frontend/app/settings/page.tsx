import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { SettingsClient } from "./SettingsClient";

export const metadata: Metadata = {
  title: "Settings | Bubbles",
  description: "Account, connection, reminders, motion and your data.",
};

export default function SettingsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <SettingsClient />
      </ApiProvider>
    </AuthProvider>
  );
}