import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { PrivacyChoicesClient } from "./PrivacyChoicesClient";

export const metadata: Metadata = {
  title: "Privacy choices | Bubbles",
  description: "Each choice is off until you turn it on. Change any of them at any time.",
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
