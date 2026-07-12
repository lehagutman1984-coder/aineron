import type { MetadataRoute } from "next";
import { serverListNetworks, serverListBlogPosts } from "@/lib/api/server";
import { routing } from "@/i18n/routing";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru").replace(/\/$/, "");

export const revalidate = 3600;

// "as-needed": дефолтная локаль инстанса без префикса, остальные — с /{locale}
function urlFor(locale: string, path: string): string {
  const prefix = locale === routing.defaultLocale ? "" : `/${locale}`;
  return `${SITE_URL}${prefix}${path}`;
}

function alternates(path: string) {
  if (routing.locales.length < 2) return undefined;
  const languages: Record<string, string> = {};
  for (const locale of routing.locales) {
    languages[locale] = urlFor(locale, path);
  }
  languages["x-default"] = urlFor(routing.defaultLocale, path);
  return { languages };
}

function entry(
  path: string,
  opts: { changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"]; priority: number; lastModified?: Date },
): MetadataRoute.Sitemap[number] {
  return {
    url: urlFor(routing.defaultLocale, path),
    lastModified: opts.lastModified ?? new Date(),
    changeFrequency: opts.changeFrequency,
    priority: opts.priority,
    alternates: alternates(path),
  };
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [networks, posts] = await Promise.all([
    serverListNetworks().catch(() => []),
    serverListBlogPosts().catch(() => []),
  ]);

  const staticRoutes: MetadataRoute.Sitemap = [
    entry("/", { changeFrequency: "weekly", priority: 1.0 }),
    entry("/models/", { changeFrequency: "daily", priority: 0.9 }),
    entry("/blog/", { changeFrequency: "daily", priority: 0.8 }),
    entry("/docs/", { changeFrequency: "weekly", priority: 0.8 }),
    entry("/api-docs/", { changeFrequency: "monthly", priority: 0.6 }),
    entry("/sandbox/", { changeFrequency: "monthly", priority: 0.7 }),
  ];

  const networkRoutes: MetadataRoute.Sitemap = (networks ?? []).map((n) =>
    entry(`/models/${n.slug}/`, { changeFrequency: "weekly", priority: 0.85 }),
  );

  const postRoutes: MetadataRoute.Sitemap = (posts ?? []).map((p) =>
    entry(`/blog/${p.slug}/`, {
      changeFrequency: "monthly",
      priority: 0.7,
      lastModified: new Date(p.published_at),
    }),
  );

  return [...staticRoutes, ...networkRoutes, ...postRoutes];
}
