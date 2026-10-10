import type { NextConfig } from "next";

// The old throwaway Vercel addresses of the production project. Anyone who lands on one (an email link, a bookmark) is sent to the real
// site: the API only accepts requests from heybubbles.in, so the app cannot work from these addresses. A redirect keeps the path, the
// query and (in the browser) the #fragment, so sign-in links still complete. Preview deployments are not listed and stay reachable.
const LEGACY_HOSTS = ["bubbles-7x74.vercel.app", "bubbles-7x74-hey-bubbles.vercel.app"];
const CONFIGURED = (process.env.NEXT_PUBLIC_SITE_URL || "").replace(/\/+$/, "");
// A site address that is itself one of the legacy hosts would redirect to itself forever, so it is ignored.
const SITE = CONFIGURED && !LEGACY_HOSTS.some((host) => CONFIGURED.includes(host)) ? CONFIGURED : "https://heybubbles.in";

const nextConfig: NextConfig = {
  // Lets a second local server (e.g. a dev server used for testing) build into its
  // own folder so it never corrupts the `.next` of a server that is already running.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async redirects() {
    return LEGACY_HOSTS.map((host) => ({
      source: "/:path*",
      has: [{ type: "host" as const, value: host }],
      destination: `${SITE}/:path*`,
      permanent: false,
    }));
  },
};

export default nextConfig;
