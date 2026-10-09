import { Metadata } from "next";
import { AuthProvider } from "../../components/Providers";
import { ApiProvider } from "../../components/Providers";
import { CycleClient } from "./CycleClient";

export const metadata: Metadata = {
  title: "Cycle Tracking | Bubbles",
  description: "Period tracking, predictions, and cycle context for health insights.",
};

export default function CyclePage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <CycleClient />
      </ApiProvider>
    </AuthProvider>
  );
}