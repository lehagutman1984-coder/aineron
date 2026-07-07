import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  staticPageGenerationTimeout: 120,

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
      { source: "/accounts/:path*", destination: `${djangoUrl}/accounts/:path*` },
    ];
  },
};

export default withNextIntl(nextConfig);
