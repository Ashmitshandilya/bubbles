import type { MetadataRoute } from "next";

const SITE = (process.env.NEXT_PUBLIC_SITE_URL || "https://heybubbles.in").replace(/\/+$/, "");

// Private share links must never be indexed, even after launch. The app itself (signed-in pages) has nothing for a crawler to read.
const PRIVATE = ["/partner", "/cycle/partner", "/callback"];
const APP = ["/dashboard", "/companion", "/insights", "/health", "/cycle", "/fitness", "/care", "/profile", "/settings"];

export default function robots(): MetadataRoute.Robots {
  const open = process.env.NEXT_PUBLIC_ALLOW_INDEXING === "true";
  if (!open) return { rules: { userAgent: "*", disallow: ["/", ...PRIVATE] } };
  return { rules: { userAgent: "*", allow: "/", disallow: [...PRIVATE, ...APP] }, sitemap: `${SITE}/sitemap.xml`, host: SITE };
}

// Generated once at build time (also required by the Android app's static export).
export const dynamic = "force-static";
