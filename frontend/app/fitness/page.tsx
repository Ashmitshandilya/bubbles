import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { FitnessClient } from "./FitnessClient";

export const metadata: Metadata = {
  title: "Fitness | Bubbles",
  description: "Your day in calories, meals, workouts and progress, all as honest estimates.",
};

export default function FitnessPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <FitnessClient />
      </ApiProvider>
    </AuthProvider>
  );
}
