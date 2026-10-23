import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { MapClient } from "../MapClient";

export const metadata: Metadata = {
  title: "Understand them | Bubbles",
  description: "What you know about someone, and what to ask.",
  robots: { index: false },
};

export default function MapPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <MapClient />
      </ApiProvider>
    </AuthProvider>
  );
}
