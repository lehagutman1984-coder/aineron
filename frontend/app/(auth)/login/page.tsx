"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { authLogin } from "@/lib/api/client";
import { APIError } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { setUser } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const next = params.get("next") ?? "/account/";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const user = await authLogin(email.trim().toLowerCase(), password);
      setUser(user);
      router.push(next);
    } catch (err) {
      setError(
        err instanceof APIError ? err.message : "Ошибка входа. Попробуйте снова."
      );
      setLoading(false);
    }
  };

  return (
    <div className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 shadow-sm">
      <h1 className="mb-1 text-[22px] font-bold text-[#0d0d0d]">Войти</h1>
      <p className="mb-6 text-[14px] text-[rgba(13,13,13,0.55)]">
        Нет аккаунта?{" "}
        <Link href="/register/" className="text-[#0a7cff] hover:underline underline-offset-2">
          Зарегистрироваться
        </Link>
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-[#0d0d0d]">
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            placeholder="you@example.com"
            className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3.5 py-2.5 text-[14px] text-[#0d0d0d] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] transition-all"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-[13px] font-medium text-[#0d0d0d]">
            Пароль
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            placeholder="Минимум 8 символов"
            className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3.5 py-2.5 text-[14px] text-[#0d0d0d] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] transition-all"
          />
        </div>

        {error && (
          <div className="rounded-[8px] bg-[rgba(231,76,60,0.08)] px-3.5 py-2.5 text-[13px] text-[#e74c3c]">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="mt-1 h-10 w-full rounded-[8px] bg-[#0a7cff] text-[14px] font-medium text-white hover:bg-[#0066cc] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Вход..." : "Войти"}
        </button>
      </form>

      <div className="mt-5 border-t border-[rgba(13,13,13,0.08)] pt-5">
        <a
          href="/users/pages/auth/?tab=reset"
          className="block text-center text-[13px] text-[rgba(13,13,13,0.5)] hover:text-[#0a7cff] transition-colors"
        >
          Забыли пароль?
        </a>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 h-64" />}>
      <LoginForm />
    </Suspense>
  );
}
