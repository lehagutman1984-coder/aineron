"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { useAuthStore } from "@/lib/stores/auth";

type Placement = "hero" | "pricing" | "final";

/**
 * CTA-группа лендинга с учётом авторизации.
 * Залогиненного пользователя ведём в кабинет, гостя — на регистрацию.
 * До гидрации рендерим гостевой вариант, чтобы не было mismatch между SSR и клиентом.
 */
export function HomeCta({ placement }: { placement: Placement }) {
  const user = useAuthStore((s) => s.user);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const authed = mounted && !!user;

  if (placement === "pricing") {
    return (
      <Link
        href={authed ? "/account/billing/" : "/register/"}
        className="inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-8 py-3 text-[16px] font-medium text-white transition-colors hover:bg-[#C4623E]"
      >
        {authed ? "Пополнить баланс" : "Начать с 10 ₽ бесплатно"}
        <ArrowRight size={15} />
      </Link>
    );
  }

  if (placement === "final") {
    return (
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link
          href={authed ? "/account/" : "/register/"}
          className="inline-flex items-center gap-2 rounded-[10px] bg-white px-7 py-3 text-[17px] font-medium text-[#1A1A1A] transition-colors hover:bg-[rgba(255,255,255,0.90)]"
        >
          {authed ? "Открыть кабинет" : "Создать аккаунт"}
          <ArrowRight size={16} />
        </Link>
        <Link
          href="/models/"
          className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(255,255,255,0.45)] bg-[rgba(255,255,255,0.10)] px-7 py-3 text-[17px] font-medium text-white transition-colors hover:border-[rgba(255,255,255,0.65)] hover:bg-[rgba(255,255,255,0.18)]"
        >
          Смотреть модели
        </Link>
      </div>
    );
  }

  // hero
  return (
    <div className="flex flex-wrap items-center justify-center gap-3">
      <Link
        href={authed ? "/account/" : "/register/"}
        className="inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-7 py-3 text-[17px] font-medium text-white transition-colors hover:bg-[#C4623E]"
      >
        {authed ? "Открыть кабинет" : "Начать бесплатно"}
        <ArrowRight size={16} />
      </Link>
      <Link
        href="/models/"
        className="inline-flex items-center gap-2 rounded-[10px] border border-[var(--border-primary)] bg-[var(--card-bg)] px-7 py-3 text-[17px] font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--background-secondary)]"
      >
        {authed ? "Новый чат" : "Смотреть каталог"}
      </Link>
    </div>
  );
}
