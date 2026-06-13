import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",

  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "aineron.ru",
        pathname: "/media/**",
      },
    ],
  },

  async rewrites() {
    const djangoUrl = process.env.DJANGO_INTERNAL_URL ?? "http://web:8000";
    return [
      { source: "/api/:path*",      destination: `${djangoUrl}/api/:path*` },
      { source: "/admin/:path*",    destination: `${djangoUrl}/admin/:path*` },
      { source: "/users/:path*",    destination: `${djangoUrl}/users/:path*` },
      { source: "/aitext/:path*",   destination: `${djangoUrl}/aitext/:path*` },
      { source: "/blog/:path*",     destination: `${djangoUrl}/blog/:path*` },
      { source: "/accounts/:path*", destination: `${djangoUrl}/accounts/:path*` },
      // sitemap.xml and robots.txt handled natively by Next.js (app/sitemap.ts, app/robots.ts)
    ];
  },
};

export default nextConfig;
