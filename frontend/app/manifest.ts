import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Bubbles",
    short_name: "Bubbles",
    description: "Your personal health companion.",
    start_url: "/dashboard",
    display: "standalone",
    background_color: "#FFF6FA",
    theme_color: "#FFF6FA",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/apple-icon.png", sizes: "180x180", type: "image/png" },
    ],
  };
}
