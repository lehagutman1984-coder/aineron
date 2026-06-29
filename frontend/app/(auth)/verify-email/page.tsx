"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Mail } from "lucide-react";
import { authVerifyEmail, authResendVerification } from "@/lib/api/client";
import { APIError } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";

const RESEND_TIMEOUT = 60;

function VerifyEmailForm() {
  const router = useRouter();
  const { user, setUser } = useAuthStore();
  const [digits, setDigits] = useState(["", "", "", "", "", ""]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resendCountdown, setResendCountdown] = useState(RESEND_TIMEOUT);
  const [resendLoading, setResendLoading] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (user?.email_verified) {
      // If onboarding not done yet, send to welcome; otherwise account
      const done = typeof window !== "undefined" && localStorage.getItem("onboarding_done") === "1";
      router.replace(done ? "/account/" : "/welcome/");
    }
  }, [user, router]);

  useEffect(() => {
    if (resendCountdown <= 0) return;
    const t = setTimeout(() => setResendCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [resendCountdown]);

  const handleChange = (index: number, value: string) => {
    const digit = value.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[index] = digit;
    setDigits(next);
    if (digit && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
    if (next.every((d) => d !== "")) {
      handleSubmit(next.join(""));
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pasted.length === 6) {
      setDigits(pasted.split(""));
      inputRefs.current[5]?.focus();
      handleSubmit(pasted);
    }
  };

  const handleSubmit = async (code: string) => {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      await authVerifyEmail(code);
      if (user) setUser({ ...user, email_verified: true });
      // New users go through onboarding; /welcome/ checks localStorage and skips if already done
      router.push("/welcome/");
    } catch (err) {
      setError(err instanceof APIError ? err.message : "Неверный код. Попробуйте снова.");
      setDigits(["", "", "", "", "", ""]);
      inputRefs.current[0]?.focus();
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (resendCountdown > 0 || resendLoading) return;
    setResendLoading(true);
    setResendSuccess(false);
    try {
      await authResendVerification();
      setResendSuccess(true);
      setResendCountdown(RESEND_TIMEOUT);
    } catch {
      setError("Не удалось отправить письмо. Попробуйте позже.");
    } finally {
      setResendLoading(false);
    }
  };

  return (
    <div className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 shadow-sm text-center">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(10,124,255,0.08)]">
        <Mail size={24} className="text-[#D97757]" />
      </div>
      <h1 className="mb-1 text-[22px] font-bold text-[#1A1A1A]">Подтвердите email</h1>
      <p className="mb-6 text-[14px] text-[rgba(13,13,13,0.55)]">
        Мы отправили 6-значный код на{" "}
        <span className="font-medium text-[#1A1A1A]">{user?.email ?? "вашу почту"}</span>
      </p>

      <div className="mb-5 flex justify-center gap-2" onPaste={handlePaste}>
        {digits.map((digit, i) => (
          <input
            key={i}
            ref={(el) => { inputRefs.current[i] = el; }}
            type="text"
            inputMode="numeric"
            maxLength={1}
            value={digit}
            onChange={(e) => handleChange(i, e.target.value)}
            onKeyDown={(e) => handleKeyDown(i, e)}
            disabled={loading}
            className="h-12 w-10 rounded-[8px] border border-[rgba(13,13,13,0.15)] text-center text-[20px] font-bold text-[#1A1A1A] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] transition-all disabled:opacity-50"
          />
        ))}
      </div>

      {error && (
        <div className="mb-4 rounded-[8px] bg-[rgba(231,76,60,0.08)] px-3.5 py-2.5 text-[13px] text-[#e74c3c]">
          {error}
        </div>
      )}

      {resendSuccess && (
        <div className="mb-4 rounded-[8px] bg-[rgba(29,214,193,0.10)] px-3.5 py-2.5 text-[13px] text-[#0d9e8c]">
          Письмо отправлено повторно
        </div>
      )}

      <button
        onClick={() => handleSubmit(digits.join(""))}
        disabled={loading || digits.some((d) => !d)}
        className="mb-4 h-10 w-full rounded-[8px] bg-[#D97757] text-[14px] font-medium text-white hover:bg-[#0066cc] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? "Проверяем..." : "Подтвердить"}
      </button>

      <button
        onClick={handleResend}
        disabled={resendCountdown > 0 || resendLoading}
        className="text-[13px] text-[rgba(13,13,13,0.55)] hover:text-[#D97757] disabled:cursor-not-allowed transition-colors"
      >
        {resendCountdown > 0
          ? `Отправить повторно через ${resendCountdown} сек.`
          : resendLoading
          ? "Отправляем..."
          : "Отправить код повторно"}
      </button>

      <div className="mt-6 border-t border-[rgba(13,13,13,0.08)] pt-4">
        <Link href="/" className="text-[13px] text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A] transition-colors">
          На главную
        </Link>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 h-64" />}>
      <VerifyEmailForm />
    </Suspense>
  );
}
