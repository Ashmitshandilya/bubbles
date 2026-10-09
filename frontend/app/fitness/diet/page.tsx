import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { DietClient } from "./DietClient";

export const metadata: Metadata = {
  title: "Diet planner | Bubbles",
  description: "A week of meals that fit your food, allergies and estimates, with swaps and a grocery list.",
};

export default function DietPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <DietClient />
      </ApiProvider>
    </AuthProvider>
  );
}
