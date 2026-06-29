import { ShieldOff } from "lucide-react";
import Link from "next/link";

export const metadata = {
  title: "Аккаунт заблокирован",
  robots: "noindex",
};

export default function BlockedPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f5f5f7] px-4">
      <div className="w-full max-w-md rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 shadow-sm text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(231,76,60,0.08)]">
          <ShieldOff size={24} className="text-[#e74c3c]" />
        </div>
        <h1 className="mb-2 text-[22px] font-bold text-[#0d0d0d]">Аккаунт заблокирован</h1>
        <p className="mb-6 text-[14px] text-[rgba(13,13,13,0.55)] leading-relaxed">
          Ваш аккаунт заблокирован в связи с нарушением правил использования сервиса.
          Если вы считаете, что это ошибка, свяжитесь с поддержкой.
        </p>
        <a
          href="mailto:support@aineron.ru"
          className="mb-4 flex h-10 w-full items-center justify-center rounded-[8px] bg-[#f0a38a] text-[14px] font-medium text-white hover:bg-[#0066cc] transition-colors"
        >
          Написать в поддержку
        </a>
        <div className="border-t border-[rgba(13,13,13,0.08)] pt-4">
          <Link
            href="/"
            className="text-[13px] text-[rgba(13,13,13,0.45)] hover:text-[#0d0d0d] transition-colors"
          >
            На главную
          </Link>
        </div>
      </div>
    </div>
  );
}
