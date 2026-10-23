import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { HarborClient } from "../HarborClient";

export const metadata: Metadata = {
  title: "Feeling unsafe at home? | Bubbles",
  description: "Help lines and a private safety plan.",
  robots: { index: false },
};

export default function HarborPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <HarborClient />
      </ApiProvider>
    </AuthProvider>
  );
}
