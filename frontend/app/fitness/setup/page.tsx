import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { SetupClient } from "./SetupClient";

export const metadata: Metadata = {
  title: "Fitness setup | Bubbles",
  description: "Tell Bubbles a few body details so your fitness numbers fit you. Only what is needed, and you can skip the rest.",
};

export default function FitnessSetupPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <SetupClient />
      </ApiProvider>
    </AuthProvider>
  );
}
