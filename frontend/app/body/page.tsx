import { Metadata } from "next";
import { ApiProvider, AuthProvider } from "../../components/Providers";
import { BodyClient } from "./BodyClient";

export const metadata: Metadata = {
  title: "Body map | Bubbles",
  description: "What your entries say about each part of the body, how sure Bubbles is, and what is still missing. Not a diagnosis.",
};

export default function BodyPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <BodyClient />
      </ApiProvider>
    </AuthProvider>
  );
}
