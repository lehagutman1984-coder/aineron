"use client";

import { useState } from "react";
import { Link } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { ajaxPasswordReset } from "@/lib/api/client";

export default function ForgotPasswordPage() {
  const t = useTranslations("auth");

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      // Ответ backend'а (success/message) намеренно игнорируется: поле message
      // прямо палит, зарегистрирован ли email в системе ("Пользователь с таким
      // email не найден" vs "Новый пароль отправлен"). Показываем один и тот же
      // нейтральный текст при любом завершённом запросе — так это работает у
      // всех, кто относится к user enumeration серьёзно.
      await ajaxPasswordReset(email.trim().toLowerCase());
      setSuccess(true);
    } catch {
      setError(t("forgotPasswordError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 shadow-sm">
      <h1 className="mb-1 text-[22px] font-bold text-[#1A1A1A]">{t("forgotPasswordTitle")}</h1>
      <p className="mb-6 text-[16px] text-[rgba(13,13,13,0.55)]">
        {t("forgotPasswordDescription")}
      </p>

      {success ? (
        <div className="rounded-[8px] bg-[rgba(217,119,87,0.10)] px-3.5 py-2.5 text-[15px] text-[#D97757]">
          {t("forgotPasswordSuccess")}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-[15px] font-medium text-[#1A1A1A]">
              {t("email")}
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              placeholder="you@example.com"
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3.5 py-2.5 text-[16px] text-[#1A1A1A] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
            />
          </div>

          {error && (
            <div className="rounded-[8px] bg-[rgba(231,76,60,0.08)] px-3.5 py-2.5 text-[15px] text-[#e74c3c]">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-1 h-10 w-full rounded-[8px] bg-[#D97757] text-[16px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? t("forgotPasswordSending") : t("forgotPasswordButton")}
          </button>
        </form>
      )}

      <div className="mt-5 border-t border-[rgba(13,13,13,0.08)] pt-5">
        <Link
          href="/login/"
          className="block text-center text-[15px] text-[rgba(13,13,13,0.5)] hover:text-[#D97757] transition-colors"
        >
          {t("backToLogin")}
        </Link>
      </div>
    </div>
  );
}
