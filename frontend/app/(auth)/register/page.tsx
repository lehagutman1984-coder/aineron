"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Check } from "lucide-react";
import { authRegister } from "@/lib/api/client";
import { APIError } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";

function RegisterForm() {
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
    if (password.length < 8) {
      setError("Пароль должен содержать минимум 8 символов");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const user = await authRegister(email.trim().toLowerCase(), password);
      setUser(user);
      router.push("/verify-email/");
    } catch (err) {
      setError(
        err instanceof APIError ? err.message : "Ошибка регистрации. Попробуйте снова."
      );
      setLoading(false);
    }
  };

  return (
    <div className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 shadow-sm">
      <h1 className="mb-1 text-[22px] font-bold text-[#1A1A1A]">Создать аккаунт</h1>
      <p className="mb-6 text-[16px] text-[rgba(13,13,13,0.55)]">
        Уже есть аккаунт?{" "}
        <Link href="/login/" className="text-[#D97757] hover:underline underline-offset-2">
          Войти
        </Link>
      </p>

      <div className="mb-5 flex items-center gap-2 rounded-[8px] bg-[rgba(217,119,87,0.10)] px-3.5 py-2.5 text-[15px] text-[#D97757]">
        <Check size={14} />
        10 звёзд бесплатно при регистрации
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label className="mb-1.5 block text-[15px] font-medium text-[#1A1A1A]">
            Email
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
        <div>
          <label className="mb-1.5 block text-[15px] font-medium text-[#1A1A1A]">
            Пароль
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
            placeholder="Минимум 8 символов"
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
          {loading ? "Создаём аккаунт..." : "Создать аккаунт"}
        </button>
      </form>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 h-64" />}>
      <RegisterForm />
    </Suspense>
  );
}
