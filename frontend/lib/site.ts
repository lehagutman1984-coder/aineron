export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru";

export function siteHost(): string {
  return new URL(SITE_URL).host;
}

export function brandName(): string {
  const host = siteHost();
  return host.charAt(0).toUpperCase() + host.slice(1);
}

export function supportEmail(): string {
  return `support@${siteHost()}`;
}
