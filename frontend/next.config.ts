import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Emits a self-contained server bundle so the production image can drop
  // node_modules entirely.
  output: "standalone",
};

export default nextConfig;
