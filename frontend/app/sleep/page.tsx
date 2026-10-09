import { Metadata } from "next";
import { AuthProvider } from "../../components/Providers";
import { ApiProvider } from "../../components/Providers";
import { SleepClient } from "./SleepClient";

export const metadata: Metadata = {
  title: "Sleep Tracking | Bubbles",
  description: "Sleep duration, quality, and recovery patterns.",
};

export default function SleepPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <SleepClient />
      </ApiProvider>
    </AuthProvider>
  );
}