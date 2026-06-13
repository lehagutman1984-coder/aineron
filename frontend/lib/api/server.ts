// Server-side fetch helper for Next.js Server Components (RSC / SSG / SSR).
// Uses the internal Docker network URL so fetches bypass Nginx entirely.

import type { NetworkListItem, NetworkDetail, Category } from "./types";

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
