import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { FightClient } from "../FightClient";

export const metadata: Metadata = {
  title: "After a fight | Bubbles",
  description: "Turn the hard moment into a calm message.",
  robots: { index: false },
};

export default function FightPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <FightClient />
      </ApiProvider>
    </AuthProvider>
  );
}
