import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { MedicationsClient } from "./MedicationsClient";

export const metadata: Metadata = {
  title: "Medications | Bubbles",
  description: "Your medicines, today's doses, refills and a printable logbook.",
};

export default function MedicationsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <MedicationsClient />
      </ApiProvider>
    </AuthProvider>
  );
}
