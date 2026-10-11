import type { NextConfig } from "next";

// The old throwaway Vercel addresses of the production project. Anyone who lands on one (an email link, a bookmark) is sent to the real
// site: the API only accepts requests from heybubbles.in, so the app cannot work from these addresses. A redirect keeps the path, the
// query and (in the browser) the #fragment, so sign-in links still complete. Preview deployments are not listed and stay reachable.
const LEGACY_HOSTS = ["bubbles-7x74.vercel.app", "bubbles-7x74-hey-bubbles.vercel.app"];
const CONFIGURED = (process.env.NEXT_PUBLIC_SITE_URL || "").replace(/\/+$/, "");
// A site address that is itself one of the legacy hosts would redirect to itself forever, so it is ignored.
const SITE = CONFIGURED && !LEGACY_HOSTS.some((host) => CONFIGURED.includes(host)) ? CONFIGURED : "https://heybubbles.in";

/** The origin (scheme + host) of an address, or null when it is not a usable URL. */
function originOf(address: string | undefined): string | null {
  try {
    return address ? new URL(address).origin : null;
  } catch {
    return null;
  }
}

/**
 * Where the browser is allowed to talk to. Only the API and the sign-in service: a script that somehow ran could not send data anywhere else.
 * The addresses come from the same build variables the app itself uses; if the Supabase one is missing the whole *.supabase.co family is allowed.
 */
function connectSources(): string[] {
  const api = originOf(process.env.NEXT_PUBLIC_API_URL) ?? "https://bubbles-dk3v.onrender.com";
  const supabase = originOf(process.env.NEXT_PUBLIC_SUPABASE_URL);
  const auth = supabase ? [supabase, supabase.replace(/^https:/, "wss:")] : ["https://*.supabase.co", "wss://*.supabase.co"];
  return ["'self'", api, ...auth];
}

/**
 * Content Security Policy for production pages. Scripts need 'unsafe-inline' because Next.js streams small inline scripts to hydrate each page;
 * everything else is closed: no plugins, no framing, no other form targets, no other base address, nothing loaded over plain http.
 */
export function contentSecurityPolicy(): string {
  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "media-src 'self' blob: data:",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    `connect-src ${connectSources().join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests",
  ].join("; ");
}

const SECURITY_HEADERS = [
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "X-DNS-Prefetch-Control", value: "off" },
];

const nextConfig: NextConfig = {
  // Lets a second local server (e.g. a dev server used for testing) build into its
  // own folder so it never corrupts the `.next` of a server that is already running.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Browser source maps are never published: nobody should be able to read the original source from the live site.
  productionBrowserSourceMaps: false,
  // The framework name is not advertised in a response header.
  poweredByHeader: false,
  async redirects() {
    return LEGACY_HOSTS.map((host) => ({
      source: "/:path*",
      has: [{ type: "host" as const, value: host }],
      destination: `${SITE}/:path*`,
      permanent: false,
    }));
  },
  async headers() {
    const production = process.env.NODE_ENV === "production";
    return [
      // The CSP is production only: the dev server needs eval and a websocket for hot reload.
      { source: "/:path*", headers: production ? [...SECURITY_HEADERS, { key: "Content-Security-Policy", value: contentSecurityPolicy() }] : SECURITY_HEADERS.filter((h) => h.key !== "Strict-Transport-Security") },
      // Share links carry a secret token in the address: never send it to another site as a referrer.
      { source: "/partner/:path*", headers: [{ key: "Referrer-Policy", value: "no-referrer" }] },
      { source: "/cycle/partner/:path*", headers: [{ key: "Referrer-Policy", value: "no-referrer" }] },
    ];
  },
};

export default nextConfig;
