import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { CareClient } from "./CareClient";

export const metadata: Metadata = {
  title: "Doctor prep | Bubbles",
  description: "Questions, a timeline and a printable summary for your next appointment. Bubbles does not diagnose.",
};

export default function CarePage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <CareClient />
      </ApiProvider>
    </AuthProvider>
  );
}