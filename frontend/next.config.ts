import type { NextConfig } from "next";

// The Django API. The site proxies /api and /media to it, so the browser only ever talks
// to one origin and the sign-in cookies stay first-party.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    // Match logs go through the /api rewrite when Caddy isn't in front (local Docker):
    // debugger logs are 50 MB+ and the default limit is 10 MB.
    proxyClientMaxBodySize: "320mb",
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/media/:path*", destination: `${API_URL}/media/:path*` },
    ];
  },
};

export default nextConfig;
