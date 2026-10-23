import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { OrbitHomeClient } from "./OrbitHomeClient";

export const metadata: Metadata = {
  title: "Orbit | Bubbles",
  description: "A quiet place for the people closest to you.",
  robots: { index: false },
};

export default function OrbitPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <OrbitHomeClient />
      </ApiProvider>
    </AuthProvider>
  );
}
