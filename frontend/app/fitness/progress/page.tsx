import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { ProgressClient } from "./ProgressClient";

export const metadata: Metadata = {
  title: "Progress | Bubbles",
  description: "Your weight trend, measurements and consistency, shown as trends rather than single days.",
};

export default function ProgressPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <ProgressClient />
      </ApiProvider>
    </AuthProvider>
  );
}
