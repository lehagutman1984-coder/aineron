import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Inter, Vazirmatn } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { routing, RTL_LOCALES, type AppLocale } from "@/i18n/routing";
import "../globals.css";
import { Providers } from "./providers";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { AuthInit } from "@/components/layout/AuthInit";
import { ThemeProvider } from "@/components/layout/ThemeProvider";
import { ToastContainer } from "@/components/ui/toast";
import { Analytics } from "@/components/analytics/Analytics";
import { PWAProvider } from "@/components/PWAProvider";

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-inter",
  display: "swap",
});

// fa (G4). ar — своя гарнитура при добавлении в G5 (см. globals.css).
const vazirmatn = Vazirmatn({
  subsets: ["arabic", "latin"],
  variable: "--font-vazirmatn",
  display: "swap",
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru";
const SITE_HOST = new URL(SITE_URL).host;

const OG_LOCALES: Record<string, string> = {
  ru: "ru_RU",
  en: "en_US",
  fa: "fa_IR",
  tr: "tr_TR",
  id: "id_ID",
  ar: "ar_SA",
};

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "rootMeta" });
  return {
    title: {
      default: t("defaultTitle", { host: SITE_HOST }),
      template: `%s — ${SITE_HOST}`,
    },
    description: t("description"),
    metadataBase: new URL(SITE_URL),
    openGraph: {
      locale: OG_LOCALES[locale] ?? "en_US",
      type: "website",
      siteName: SITE_HOST,
    },
    twitter: {
      card: "summary_large_image",
    },
    manifest: "/manifest.webmanifest",
    appleWebApp: {
      capable: true,
      title: "aineron",
      statusBarStyle: "default",
    },
    icons: {
      icon: [
        { url: "/favicon.ico", sizes: "48x48" },
        { url: "/icons/icon.svg", type: "image/svg+xml" },
      ],
      apple: "/icons/icon-192.png",
    },
  };
}

export default async function RootLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}>) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as AppLocale)) notFound();
  // Разрешает next-intl использовать static rendering для этого сегмента
  // вместо принудительного dynamic — иначе generateStaticParams выше не даёт эффекта.
  setRequestLocale(locale);
  const messages = await getMessages();
  return (
    <html
      lang={locale}
      dir={RTL_LOCALES.includes(locale) ? "rtl" : "ltr"}
      className={`${inter.variable} ${vazirmatn.variable}`}
    >
      <head>
        {/* Anti-FOUC: apply theme before React hydrates to avoid flash */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('aineron-theme')||'system';var d=t==='dark'||(t==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.setAttribute('data-theme',d?'dark':'light');}catch(e){}})();`,
          }}
        />
      </head>
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>
        <Providers>
          <ThemeProvider />
          <AuthInit />
          <Navbar />
          <main>{children}</main>
          <Footer />
          <ToastContainer />
          <Analytics />
          <PWAProvider />
        </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
