import { notFound } from "next/navigation";
import PearlGallery from "./Gallery";

// Component screenshots for design review. Exists only when the dev preview flag is set at build time.
export default function Page() {
  if (process.env.NEXT_PUBLIC_UI_PREVIEW !== "1") notFound();
  return <PearlGallery />;
}
