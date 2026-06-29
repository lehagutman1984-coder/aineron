import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "aineron.ru — AI без VPN",
    short_name: "aineron",
    description:
      "GPT-4o, Claude, Gemini и другие нейросети без VPN. Чат и генерация изображений.",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#f0a38a",
    orientation: "portrait-primary",
    lang: "ru",
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
        name: "Новый чат",
        url: "/catalog/",
        description: "Выбрать нейросеть и начать чат",
      },
      {
        name: "Кабинет",
        url: "/account/",
        description: "Баланс и настройки",
      },
    ],
  };
}
