import type { MetadataRoute } from "next";

// Private share links must never be indexed, even after launch.
const PRIVATE = ["/partner", "/cycle/partner"];

export default function robots(): MetadataRoute.Robots {
  const open = process.env.NEXT_PUBLIC_ALLOW_INDEXING === "true";
  return { rules: open ? { userAgent: "*", allow: "/", disallow: PRIVATE } : { userAgent: "*", disallow: ["/", ...PRIVATE] } };
}
