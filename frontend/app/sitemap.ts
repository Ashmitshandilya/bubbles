import type { MetadataRoute } from "next";

// Only the public pages. Everything behind sign-in and the private share links stay out of the sitemap.
const SITE = (process.env.NEXT_PUBLIC_SITE_URL || "https://heybubbles.in").replace(/\/+$/, "");
const UPDATED = new Date("2026-10-11");

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${SITE}/`, lastModified: UPDATED, changeFrequency: "monthly", priority: 1 },
    { url: `${SITE}/login`, lastModified: UPDATED, changeFrequency: "yearly", priority: 0.5 },
    { url: `${SITE}/privacy`, lastModified: UPDATED, changeFrequency: "yearly", priority: 0.3 },
    { url: `${SITE}/terms`, lastModified: UPDATED, changeFrequency: "yearly", priority: 0.3 },
  ];
}

// Generated once at build time (also required by the Android app's static export).
export const dynamic = "force-static";
