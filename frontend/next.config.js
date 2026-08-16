/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produces .next/standalone — a self-contained server bundle for
  // self-hosted Docker deploys (frontend/Dockerfile). Vercel ignores this
  // and uses its own build output instead, so it's harmless there too.
  output: "standalone",
  // Vercel-only: proxies browser calls to /api/v1/* through to the backend
  // server-side, so the browser only ever talks to the Vercel origin.
  // Sidesteps two problems a direct browser->gateway call would hit: mixed
  // content (this Vercel deploy is HTTPS, the free-tier gateway is plain
  // HTTP) and CORS (api-gateway's allow_origins list doesn't know about the
  // Vercel domain). See docs/deployment/vercel-frontend.md.
  //
  // No-op locally / anywhere BACKEND_ORIGIN isn't set — NEXT_PUBLIC_API_BASE_URL's
  // own localhost:8000 default (lib/session.ts) handles local dev instead.
  async rewrites() {
    const backendOrigin = process.env.BACKEND_ORIGIN;
    if (!backendOrigin) return [];
    return [
      { source: "/api/v1/:path*", destination: `${backendOrigin}/api/v1/:path*` },
    ];
  },
};

module.exports = nextConfig;
