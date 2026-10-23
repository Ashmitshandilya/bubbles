import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { TextClient } from "../TextClient";

export const metadata: Metadata = {
  title: "Before I text them | Bubbles",
  description: "Pause, then say it softly.",
  robots: { index: false },
};

export default function TextPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <TextClient />
      </ApiProvider>
    </AuthProvider>
  );
}
