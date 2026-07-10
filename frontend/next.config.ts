import type { NextConfig } from "next";

// Browser API calls go to the frontend origin (/api/...) and are proxied
// here to the FastAPI backend. This makes the dashboard work from any
// device on the network — previously the client called localhost:8000,
// which only resolves on the machine running the backend itself.
const API_URL = process.env.API_PROXY_TARGET || "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
