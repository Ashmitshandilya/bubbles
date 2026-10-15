import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Bubbles",
    short_name: "Bubbles",
    description: "Your personal health companion.",
    start_url: "/dashboard",
    display: "standalone",
    background_color: "#FBF8F6",
    theme_color: "#FBF8F6",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/apple-icon.png", sizes: "180x180", type: "image/png" },
    ],
  };
}

// Generated once at build time (also required by the Android app's static export).
export const dynamic = "force-static";
