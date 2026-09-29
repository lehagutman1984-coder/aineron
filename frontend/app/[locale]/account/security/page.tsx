"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { authChangePassword, APIError } from "@/lib/api/client";

export default function SecurityPage() {
  const t = useTranslations("accountSecurity");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const mutation = useMutation({
    mutationFn: () => authChangePassword(currentPassword, newPassword),
    onSuccess: () => {
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    },
    onError: (err) => {
      setError(err instanceof APIError ? err.message : t("genericError"));
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    if (newPassword.length < 8) {
      setError(t("passwordTooShort"));
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(t("passwordMismatch"));
      return;
    }
    mutation.mutate();
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <h1 className="mb-8 text-[22px] font-bold text-[#1A1A1A]">{t("title")}</h1>

      <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-6">
        <div className="mb-5 flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[rgba(217,119,87,0.08)]">
            <ShieldCheck size={17} className="text-[#D97757]" />
          </div>
          <div>
            <p className="text-[16px] font-medium text-[#1A1A1A]">{t("changePassword")}</p>
            <p className="text-[14px] text-[rgba(13,13,13,0.5)]">{t("changePasswordDescription")}</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-[15px] font-medium text-[#1A1A1A]">
              {t("currentPasswordLabel")}
            </label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3.5 py-2.5 text-[16px] text-[#1A1A1A] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-[15px] font-medium text-[#1A1A1A]">
              {t("newPasswordLabel")}
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              autoComplete="new-password"
              placeholder={t("newPasswordPlaceholder")}
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3.5 py-2.5 text-[16px] text-[#1A1A1A] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-[15px] font-medium text-[#1A1A1A]">
              {t("confirmPasswordLabel")}
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3.5 py-2.5 text-[16px] text-[#1A1A1A] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
            />
          </div>

          {error && (
            <div className="rounded-[8px] bg-[rgba(231,76,60,0.08)] px-3.5 py-2.5 text-[15px] text-[#e74c3c]">
              {error}
            </div>
          )}

          {success && (
            <div className="rounded-[8px] bg-[rgba(217,119,87,0.10)] px-3.5 py-2.5 text-[15px] text-[#D97757]">
              {t("success")}
            </div>
          )}

          <button
            type="submit"
            disabled={mutation.isPending}
            className="h-10 w-full rounded-[8px] bg-[#D97757] text-[16px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 disabled:cursor-not-allowed transition-colors sm:w-auto sm:px-6"
          >
            {mutation.isPending ? t("saving") : t("save")}
          </button>
        </form>
      </div>
    </div>
  );
}
