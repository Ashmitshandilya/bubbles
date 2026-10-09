import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { MindClient } from "./MindClient";

export const metadata: Metadata = {
  title: "Mind | Bubbles",
  description: "Mood check-ins, a year in pixels, a private journal and calm exercises.",
};

export default function MindPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <MindClient />
      </ApiProvider>
    </AuthProvider>
  );
}
