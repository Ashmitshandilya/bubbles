import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { ReplyClient } from "../ReplyClient";

export const metadata: Metadata = {
  title: "Help me reply | Bubbles",
  description: "Find the words for a message.",
  robots: { index: false },
};

export default function ReplyPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <ReplyClient />
      </ApiProvider>
    </AuthProvider>
  );
}
