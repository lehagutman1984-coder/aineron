// Server-side fetch helper for Next.js Server Components (RSC / SSG / SSR).
// Uses the internal Docker network URL so fetches bypass Nginx entirely.

import type { NetworkListItem, NetworkDetail, Category, BlogCategory, BlogPost, BlogPostDetail } from "./types";

const DJANGO =
  (process.env.DJANGO_INTERNAL_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function serverFetch<T>(
  path: string,
  opts: RequestInit & { revalidate?: number | false } = {}
): Promise<T | null> {
  const { revalidate = 3600, ...rest } = opts;
  try {
    const res = await fetch(`${DJANGO}/api/v1${path}`, {
      next: revalidate === false ? { revalidate: 0 } : { revalidate },
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
  category?: string;
}) => {
  const qs = new URLSearchParams();
  if (params?.is_popular) qs.set("is_popular", "1");
  if (params?.category) qs.set("category", params.category);
  const query = qs.toString();
  return serverFetch<NetworkListItem[]>(`/catalog/networks/${query ? "?" + query : ""}`);
};

export const serverListCategories = () =>
  serverFetch<Category[]>("/catalog/categories/");

export const serverGetNetwork = (slug: string) =>
  serverFetch<NetworkDetail>(`/catalog/networks/${slug}/`);

export const serverListBlogCategories = () =>
  serverFetch<BlogCategory[]>("/blog/categories/");

export const serverListBlogPosts = (params?: {
  category?: string;
  show_on_main?: boolean;
}) => {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
  if (params?.show_on_main) qs.set("show_on_main", "1");
  const query = qs.toString();
  return serverFetch<BlogPost[]>(`/blog/posts/${query ? "?" + query : ""}`);
};

export const serverGetBlogPost = (slug: string) =>
  serverFetch<BlogPostDetail>(`/blog/posts/${slug}/`);
