import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { CaloriesClient } from "./CaloriesClient";

export const metadata: Metadata = {
  title: "Calories | Bubbles",
  description: "Say what you ate, check Bubbles' estimate, then save it. Every number is an estimate with a range.",
};

export default function CaloriesPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <CaloriesClient />
      </ApiProvider>
    </AuthProvider>
  );
}
