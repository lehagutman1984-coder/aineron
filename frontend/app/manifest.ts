import type { MetadataRoute } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import { siteHost } from "@/lib/site";

export default async function manifest(): Promise<MetadataRoute.Manifest> {
  const locale = await getLocale();
  const t = await getTranslations("manifest");
  return {
    name: t("name", { host: siteHost() }),
    short_name: "aineron",
    description: t("description"),
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#D97757",
    orientation: "portrait-primary",
    lang: locale,
    categories: ["productivity", "utilities"],
    icons: [
      {
        src: "/icons/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        // @ts-expect-error purpose not in Next.js types yet
        purpose: "any maskable",
      },
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        // @ts-expect-error purpose not in Next.js types yet
        purpose: "any maskable",
      },
    ],
    shortcuts: [
      {
        name: t("shortcutNewChat"),
        url: "/catalog/",
        description: t("shortcutNewChatDesc"),
      },
      {
        name: t("shortcutAccount"),
        url: "/account/",
        description: t("shortcutAccountDesc"),
      },
    ],
  };
}
