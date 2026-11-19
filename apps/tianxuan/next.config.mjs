/** @type {import('next').NextConfig} */
const apiOrigin = process.env.TIANXUAN_API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig = {
  output: process.env.TIANXUAN_WEB_STANDALONE === "1" ? "standalone" : undefined,
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
