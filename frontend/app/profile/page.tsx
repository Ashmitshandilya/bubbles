import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { ProfileClient } from "./ProfileClient";

export const metadata: Metadata = {
  title: "Me | Bubbles",
  description: "Your details, what Bubbles remembers, and how memory needs your confirmation.",
};

export default function ProfilePage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <ProfileClient />
      </ApiProvider>
    </AuthProvider>
  );
}