import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Lets a second local server (e.g. a dev server used for testing) build into its
  // own folder so it never corrupts the `.next` of a server that is already running.
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
