import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { PrivacyChoicesClient } from "./PrivacyChoicesClient";

export const metadata: Metadata = {
  title: "Privacy choices | Bubbles",
  description: "One switch for each thing Bubbles could do with your information. Everything starts off.",
};

export default function PrivacyChoicesPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <PrivacyChoicesClient />
      </ApiProvider>
    </AuthProvider>
  );
}
