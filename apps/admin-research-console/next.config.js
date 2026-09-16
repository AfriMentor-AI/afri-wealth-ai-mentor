/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // .next/standalone for self-hosted Docker deploys, matching frontend/next.config.js.
  output: "standalone",
  // Vercel-only: proxies browser calls to /api/v1/* through to the backend
  // server-side, so the browser only ever talks to the Vercel origin.
  // Sidesteps mixed content (Vercel HTTPS → plain-HTTP gateway) and CORS.
  // No-op locally / anywhere BACKEND_ORIGIN isn't set — NEXT_PUBLIC_API_BASE_URL's
  // own localhost:8000 default handles local dev instead.
  async rewrites() {
    const backendOrigin = process.env.BACKEND_ORIGIN;
    if (!backendOrigin) return [];
    return [
      { source: "/api/v1/:path*", destination: `${backendOrigin}/api/v1/:path*` },
    ];
  },
};

module.exports = nextConfig;
