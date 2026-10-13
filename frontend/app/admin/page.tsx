import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { AdminClient } from "./AdminClient";

// Deliberately plain: the server HTML says nothing about what this page is. Only an administrator's API answer reveals the console;
// everyone else sees the ordinary "page not found" view. The real lock is on the API (backend main._admin_gate).
export const metadata: Metadata = {
  title: "Bubbles",
  robots: { index: false, follow: false },
};

export default function AdminPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <AdminClient />
      </ApiProvider>
    </AuthProvider>
  );
}
