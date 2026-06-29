import { SearchX } from "lucide-react";
import Link from "next/link";

export const metadata = {
  title: "Страница не найдена",
  robots: "noindex",
};

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#FAF9F7] px-4">
      <div className="w-full max-w-md rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 shadow-sm text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(13,13,13,0.05)]">
          <SearchX size={24} className="text-[rgba(13,13,13,0.35)]" />
        </div>
        <p className="mb-1 text-[13px] font-medium text-[rgba(13,13,13,0.35)]">404</p>
        <h1 className="mb-2 text-[22px] font-bold text-[#1A1A1A]">Страница не найдена</h1>
        <p className="mb-6 text-[14px] text-[rgba(13,13,13,0.55)]">
          Такой страницы не существует или она была перемещена.
        </p>
        <Link
          href="/"
          className="flex h-10 w-full items-center justify-center rounded-[8px] bg-[#D97757] text-[14px] font-medium text-white hover:bg-[#0066cc] transition-colors"
        >
          На главную
        </Link>
        <div className="mt-4 border-t border-[rgba(13,13,13,0.08)] pt-4">
          <Link
            href="/models/"
            className="text-[13px] text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A] transition-colors"
          >
            Каталог нейросетей
          </Link>
        </div>
      </div>
    </div>
  );
}
