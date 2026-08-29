"use client";

import { Link } from "@/i18n/navigation";
import { useAuthStore } from "@/lib/stores/auth";

/**
 * Уже вошедший пользователь не должен видеть "Начать бесплатно" → /register —
 * это либо форма логина (уже не нужна), либо повторная регистрация. Если
 * пользователь авторизован — ведём сразу в личный кабинет.
 */
export function LandingCtaButton({
  scrollHref,
  accountHref = "/account",
  authedLabel,
  anonLabel,
  className,
  onClick,
}: {
  /** Якорь для анонимного пользователя (скролл к разделу с формой) — если не задан, используется прямая ссылка /register. */
  scrollHref?: string;
  accountHref?: string;
  authedLabel: string;
  anonLabel: string;
  className?: string;
  onClick?: () => void;
}) {
  const user = useAuthStore((s) => s.user);

  if (user) {
    return (
      <Link href={accountHref} className={className} onClick={onClick}>
        {authedLabel}
      </Link>
    );
  }

  if (scrollHref) {
    return (
      <a href={scrollHref} className={className} onClick={onClick}>
        {anonLabel}
      </a>
    );
  }

  return (
    <Link href="/register" className={className} onClick={onClick}>
      {anonLabel}
    </Link>
  );
}

/** Плашка "10 ₽ на старт" в мобильном доке — это питч для регистрации,
 * авторизованному пользователю (у него уже есть свой баланс) не нужна. */
export function LandingDockNote({
  signupAmount,
  noteLabel,
}: {
  signupAmount: string;
  noteLabel: string;
}) {
  const user = useAuthStore((s) => s.user);
  if (user) return null;
  return (
    <div className="dock-note">
      <b>{signupAmount}</b>
      {noteLabel}
    </div>
  );
}
