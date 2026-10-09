import { Metadata } from "next";
import { AuthProvider } from "../../components/Providers";
import { ApiProvider } from "../../components/Providers";
import { SymptomsClient } from "./SymptomsClient";

export const metadata: Metadata = {
  title: "Symptoms Tracking | Bubbles",
  description: "Track physical and emotional symptoms day by day.",
};

export default function SymptomsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <SymptomsClient />
      </ApiProvider>
    </AuthProvider>
  );
}