import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Vibe-Coding Studio — генератор приложений | aineron.ru',
  description: 'Создавайте веб-приложения по описанию: AI-агенты пишут, ревьюят и тестируют код.',
  robots: { index: true, follow: true },
};

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
