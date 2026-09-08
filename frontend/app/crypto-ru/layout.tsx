import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../globals.css";

// Отдельный root layout ВНЕ системы локалей next-intl (routing.locales =
// en/fa/tr/id/ar, без ru) — намеренно: единственная русскоязычная страница
// на aineron.net, страница-мостик для баннера с aineron.ru "оплата криптой
// доступна на международной версии". Полноценная ru-локаль открыла бы ВЕСЬ
// сайт по /ru/* (messages/ru.json уже существует в общем с aineron.ru коде)
// и создала бы риск SEO-каннибализации с aineron.ru за одни и те же русские
// запросы — см. обсуждение с пользователем 2026-09-08. Эта страница —
// единственное исключение, noindex (см. metadata в page.tsx).
const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function CryptoRuLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={inter.variable}>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('aineron-theme')||'system';var d=t==='dark'||(t==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.setAttribute('data-theme',d?'dark':'light');}catch(e){}})();`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
