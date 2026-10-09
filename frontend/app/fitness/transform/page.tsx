import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { TransformClient } from "./TransformClient";

export const metadata: Metadata = {
  title: "Strict transformation | Bubbles",
  description: "A structured, safety-checked plan toward a target weight, with a kind screening first and weekly check-ins.",
};

export default function TransformPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <TransformClient />
      </ApiProvider>
    </AuthProvider>
  );
}
