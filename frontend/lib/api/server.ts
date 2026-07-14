import type { NetworkListItem, NetworkDetail, Category, BlogCategory, BlogPost, BlogPostDetail } from "./types";
import { siteHost } from "@/lib/site";

async function serverFetch<T>(
  path: string,
  opts: RequestInit & { revalidate?: number | false } = {}
): Promise<T | null> {
  const django = (process.env.DJANGO_INTERNAL_URL ?? "http://web:8000").replace(/\/$/, "");
  const { revalidate = false, ...rest } = opts;
  try {
    const res = await fetch(`${django}/api/v1${path}`, {
      cache: "no-store",
      headers: { Host: siteHost() },
      signal: AbortSignal.timeout(4000),
      ...rest,
    });
    if (!res.ok) return null;
    return res.json() as Promise<T>;
  } catch {
    return null;
  }
}

export const serverListNetworks = (params?: {
  is_popular?: boolean;
  is_free?: boolean;
  category?: string;
  lang?: string;
}) => {
  const qs = new URLSearchParams();
  if (params?.is_popular) qs.set("is_popular", "1");
  if (params?.is_free) qs.set("is_free", "1");
  if (params?.category) qs.set("category", params.category);
  if (params?.lang) qs.set("lang", params.lang);
  const query = qs.toString();
  return serverFetch<NetworkListItem[]>(`/catalog/networks/${query ? "?" + query : ""}`);
};

export const serverListCategories = (lang?: string) =>
  serverFetch<Category[]>(`/catalog/categories/${lang ? `?lang=${lang}` : ""}`);

export const serverGetNetwork = (slug: string, lang?: string) =>
  serverFetch<NetworkDetail>(`/catalog/networks/${slug}/${lang ? `?lang=${lang}` : ""}`);

export const serverListBlogCategories = () =>
  serverFetch<BlogCategory[]>("/blog/categories/");

export const serverListBlogPosts = (params?: {
  category?: string;
  show_on_main?: boolean;
  lang?: string;
}) => {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
  if (params?.show_on_main) qs.set("show_on_main", "1");
  if (params?.lang) qs.set("lang", params.lang);
  const query = qs.toString();
  return serverFetch<BlogPost[]>(`/blog/posts/${query ? "?" + query : ""}`);
};

export const serverGetBlogPost = (slug: string, lang?: string) =>
  serverFetch<BlogPostDetail>(`/blog/posts/${slug}/${lang ? `?lang=${lang}` : ""}`);

export interface LegalDoc {
  title: string;
  content: string;
  last_updated: string;
}

const LEGAL_PLACEHOLDER = "Содержание будет добавлено через админку";

export const serverGetLegalDoc = async (
  type: "privacy" | "terms",
  lang?: string
): Promise<LegalDoc | null> => {
  const doc = await serverFetch<LegalDoc>(`/legal/${type}/${lang ? `?lang=${lang}` : ""}`);
  if (!doc || !doc.content?.trim() || doc.content.includes(LEGAL_PLACEHOLDER)) {
    return null;
  }
  return doc;
};
