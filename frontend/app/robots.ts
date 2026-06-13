import type { MetadataRoute } from "next";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru").replace(/\/$/, "");

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/models/", "/blog/", "/api-docs/", "/ide/"],
        disallow: [
          "/api/",
          "/admin/",
          "/users/api/",
          "/aitext/",
          "/accounts/",
          "/account/",
          "/chat/",
          "/dashboard/",
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
