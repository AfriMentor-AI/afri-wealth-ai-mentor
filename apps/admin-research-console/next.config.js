/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // .next/standalone for self-hosted Docker deploys, matching frontend/next.config.js.
  output: "standalone",
};

module.exports = nextConfig;
