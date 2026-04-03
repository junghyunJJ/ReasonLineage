import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["better-sqlite3"],
  turbopack: {
    resolveAlias: {
      "@reasonforge/core": "../../packages/core/dist/index.js",
      "@reasonforge/codex": "../../packages/codex/dist/index.js",
    },
  },
};

export default nextConfig;
