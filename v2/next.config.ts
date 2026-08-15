import type { NextConfig } from "next";
import { fileURLToPath } from "url";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));
const backendBase = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const staticExport = process.env.STATIC_EXPORT === "1";

const nextConfig: NextConfig = {
  ...(staticExport ? { output: "export" as const } : {}),
  typedRoutes: true,
  turbopack: {
    root: projectRoot
  },
  async rewrites() {
    if (staticExport) return [];
    return [
      {
        source: "/api/:path*",
        destination: `${backendBase}/:path*`
      },
      {
        source: "/static/:path*",
        destination: `${backendBase}/static/:path*`
      }
    ];
  }
};

export default nextConfig;
