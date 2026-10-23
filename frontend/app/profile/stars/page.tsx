import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { StarsClient } from "./StarsClient";

export const metadata: Metadata = {
  title: "Stars lens | Bubbles",
  description: "A traditional lens, for fun and reflection. Off until you turn it on; Bubbles checks every word against what it has seen about you.",
};

export default function StarsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <StarsClient />
      </ApiProvider>
    </AuthProvider>
  );
}
