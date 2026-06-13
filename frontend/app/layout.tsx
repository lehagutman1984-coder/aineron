import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Navbar } from "@/components/layout/Navbar";
import { AuthInit } from "@/components/layout/AuthInit";
import { ToastContainer } from "@/components/ui/toast";

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "aineron.ru — AI-нейросети без VPN",
    template: "%s — aineron.ru",
  },
  description:
    "Доступ к GPT-4o, Claude, Gemini и другим нейросетям без VPN. Чат, генерация изображений, API для разработчиков.",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru"
  ),
  openGraph: {
    locale: "ru_RU",
    type: "website",
    siteName: "aineron.ru",
  },
  twitter: {
    card: "summary_large_image",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className={inter.variable}>
      <body>
        <Providers>
          <AuthInit />
          <Navbar />
          <main>{children}</main>
          <ToastContainer />
        </Providers>
      </body>
    </html>
  );
}
