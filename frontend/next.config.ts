import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

const nextConfig: NextConfig = {
  // Static export only for production builds; dev runs as a Node server
  // so rewrites (proxy) work correctly.
  ...(isDev ? {} : { output: "export" }),

  trailingSlash: true,
  images: { unoptimized: true },

  // In dev, proxy all /api/* requests to the FastAPI backend on :8000
  async rewrites() {
    if (!isDev) return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
