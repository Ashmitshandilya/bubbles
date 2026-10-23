import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { RitualClient } from "../RitualClient";

export const metadata: Metadata = {
  title: "Today's question | Bubbles",
  description: "A small question for today.",
  robots: { index: false },
};

export default function RitualPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <RitualClient />
      </ApiProvider>
    </AuthProvider>
  );
}
