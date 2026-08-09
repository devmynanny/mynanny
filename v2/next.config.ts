import type { NextConfig } from "next";
import { fileURLToPath } from "url";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));
const backendBase = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  typedRoutes: true,
  turbopack: {
    root: projectRoot
  },
  async rewrites() {
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
