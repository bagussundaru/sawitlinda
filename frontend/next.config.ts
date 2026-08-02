import type { NextConfig } from "next";

// Set when the app is served under a path prefix behind a shared reverse proxy
// (e.g. "/sawit"). Empty during local development, where it sits at the root.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Emits a self-contained server bundle so the production image can drop
  // node_modules entirely.
  output: "standalone",
  ...(basePath ? { basePath, assetPrefix: basePath } : {}),
};

export default nextConfig;
