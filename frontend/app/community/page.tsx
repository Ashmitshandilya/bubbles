import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { CommunityClient } from "./CommunityClient";

export const metadata: Metadata = {
  title: "Community | Bubbles",
  description: "Ask, answer and share with other people, under an alias if you like.",
};

export default function CommunityPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <CommunityClient />
      </ApiProvider>
    </AuthProvider>
  );
}
