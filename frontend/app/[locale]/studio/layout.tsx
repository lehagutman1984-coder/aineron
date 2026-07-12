import { redirect } from 'next/navigation';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Vibe-Coding Studio — генератор приложений | aineron.ru',
  description: 'Создавайте веб-приложения по описанию: AI-агенты пишут, ревьюят и тестируют код.',
  robots: { index: false, follow: false },
};

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  if (process.env.STUDIO_ENABLED === 'false') {
    redirect('/');
  }
  return <>{children}</>;
}
