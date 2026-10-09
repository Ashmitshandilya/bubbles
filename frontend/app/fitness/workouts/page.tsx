import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../../components/Providers";
import { WorkoutsClient } from "./WorkoutsClient";

export const metadata: Metadata = {
  title: "Workouts | Bubbles",
  description: "A gentle weekly workout plan that adapts to how you feel, after a short safety check.",
};

export default function WorkoutsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <WorkoutsClient />
      </ApiProvider>
    </AuthProvider>
  );
}
