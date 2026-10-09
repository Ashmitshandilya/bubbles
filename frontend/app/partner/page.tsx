import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { PartnerSharingClient } from "./PartnerSharingClient";

export const metadata: Metadata = {
  title: "Partner sharing | Bubbles",
  description: "Choose exactly what one trusted person can see, and stop whenever you like.",
};

export default function PartnerSharingPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <PartnerSharingClient />
      </ApiProvider>
    </AuthProvider>
  );
}
