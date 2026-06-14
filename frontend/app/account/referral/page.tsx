"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, Check, Users, Star, Banknote, ArrowDownToLine } from "lucide-react";
import { getReferral, requestReferralWithdrawal } from "@/lib/api/client";
import type { ReferralData } from "@/lib/api/types";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

const STATUS_LABELS: Record<string, string> = {
  pending: "Ожидает",
  completed: "Выполнено",
  cancelled: "Отменено",
};

export default function ReferralPage() {
  const queryClient = useQueryClient();
  const [copied, setCopied] = useState(false);
  const [showWithdrawModal, setShowWithdrawModal] = useState(false);
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [withdrawCard, setWithdrawCard] = useState("");
  const [withdrawError, setWithdrawError] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery<ReferralData>({
    queryKey: ["referral"],
    queryFn: getReferral,
  });

  const withdrawMutation = useMutation({
    mutationFn: () =>
      requestReferralWithdrawal({
        amount: parseFloat(withdrawAmount),
        card_number: withdrawCard,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["referral"] });
      setShowWithdrawModal(false);
      setWithdrawAmount("");
      setWithdrawCard("");
      setWithdrawError(null);
    },
    onError: (err: Error) => {
      setWithdrawError(err.message || "Ошибка при запросе вывода");
    },
  });

  const copyLink = () => {
    if (!data?.referral_link) return;
    navigator.clipboard.writeText(data.referral_link).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-32 rounded-[12px] bg-[rgba(13,13,13,0.06)]" />
        <div className="h-48 rounded-[12px] bg-[rgba(13,13,13,0.06)]" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-[12px] border border-[rgba(231,76,60,0.2)] bg-[rgba(231,76,60,0.05)] p-6 text-[14px] text-[#e74c3c]">
        Не удалось загрузить данные реферальной программы
      </div>
    );
  }

  return (
    <div className="px-4 py-10 sm:px-6 space-y-6">
      <div>
        <h1 className="text-[22px] font-bold text-[#0d0d0d]">Партнёрская программа</h1>
        <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.55)]">
          Приглашайте друзей и получайте бонусы за каждую их покупку
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
          <div className="mb-1 flex items-center gap-2 text-[12px] text-[rgba(13,13,13,0.45)]">
            <Users size={14} />
            Переходов
          </div>
          <div className="text-[24px] font-bold text-[#0d0d0d]">{data.referral_clicks}</div>
        </div>

        <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
          <div className="mb-1 flex items-center gap-2 text-[12px] text-[rgba(13,13,13,0.45)]">
            {data.balance_type === "rub" ? <Banknote size={14} /> : <Star size={14} />}
            {data.balance_type === "rub" ? "Баланс (руб.)" : "Баланс (звёзды)"}
          </div>
          <div className="text-[24px] font-bold text-[#0d0d0d]">
            {data.balance_type === "rub"
              ? `${data.balance.toFixed(2)} ₽`
              : data.balance}
          </div>
        </div>

        {data.can_withdraw && (
          <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-4 flex flex-col justify-between">
            <div className="mb-1 text-[12px] text-[rgba(13,13,13,0.45)]">Вывод средств</div>
            <button
              onClick={() => setShowWithdrawModal(true)}
              className="flex items-center gap-2 rounded-[8px] bg-[#0a7cff] px-3 py-2 text-[13px] font-medium text-white hover:bg-[#0066cc] transition-colors"
            >
              <ArrowDownToLine size={14} />
              Запросить
            </button>
          </div>
        )}
      </div>

      {/* Referral link */}
      <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5">
        <div className="mb-3 text-[13px] font-medium text-[rgba(13,13,13,0.65)]">Ваша реферальная ссылка</div>
        <div className="flex items-center gap-2">
          <div className="flex-1 truncate rounded-[8px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.03)] px-3 py-2 text-[13px] font-mono text-[#0d0d0d]">
            {data.referral_link}
          </div>
          <button
            onClick={copyLink}
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[8px] border border-[rgba(13,13,13,0.12)] bg-white hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            {copied ? (
              <Check size={16} className="text-[#1dd6c1]" />
            ) : (
              <Copy size={16} className="text-[rgba(13,13,13,0.55)]" />
            )}
          </button>
        </div>
      </div>

      {/* Earnings */}
      {data.earnings.length > 0 && (
        <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white">
          <div className="border-b border-[rgba(13,13,13,0.08)] px-5 py-4 text-[14px] font-medium text-[#0d0d0d]">
            Начисления
          </div>
          <div className="divide-y divide-[rgba(13,13,13,0.06)]">
            {data.earnings.map((e) => (
              <div key={e.id} className="flex items-center justify-between px-5 py-3">
                <div>
                  <div className="text-[13px] text-[#0d0d0d]">
                    {e.description || e.tariff || "Реферальный бонус"}
                  </div>
                  <div className="text-[11px] text-[rgba(13,13,13,0.45)]">{formatDate(e.created_at)}</div>
                </div>
                <div className="text-right text-[13px] font-medium text-[#0d0d0d]">
                  {e.amount_rub > 0 && <div>+{e.amount_rub.toFixed(2)} ₽</div>}
                  {e.amount_stars > 0 && <div>+{e.amount_stars} звёзд</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Withdrawals */}
      {data.withdrawals.length > 0 && (
        <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white">
          <div className="border-b border-[rgba(13,13,13,0.08)] px-5 py-4 text-[14px] font-medium text-[#0d0d0d]">
            Запросы на вывод
          </div>
          <div className="divide-y divide-[rgba(13,13,13,0.06)]">
            {data.withdrawals.map((w) => (
              <div key={w.id} className="flex items-center justify-between px-5 py-3">
                <div>
                  <div className="text-[13px] text-[#0d0d0d]">Карта {w.card_number}</div>
                  <div className="text-[11px] text-[rgba(13,13,13,0.45)]">{formatDate(w.created_at)}</div>
                </div>
                <div className="text-right">
                  <div className="text-[13px] font-medium text-[#0d0d0d]">{w.amount.toFixed(2)} ₽</div>
                  <div className="text-[11px] text-[rgba(13,13,13,0.45)]">
                    {STATUS_LABELS[w.status] ?? w.status}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.earnings.length === 0 && (
        <div className="rounded-[12px] border border-[rgba(13,13,13,0.08)] bg-white p-8 text-center">
          <Users size={32} className="mx-auto mb-3 text-[rgba(13,13,13,0.20)]" />
          <p className="text-[14px] font-medium text-[#0d0d0d]">Пока нет начислений</p>
          <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.45)]">
            Поделитесь реферальной ссылкой, чтобы начать зарабатывать
          </p>
        </div>
      )}

      {/* Withdraw modal */}
      {showWithdrawModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
          onClick={() => setShowWithdrawModal(false)}
        >
          <div
            className="w-full max-w-sm rounded-[16px] bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="mb-4 text-[18px] font-bold text-[#0d0d0d]">Запросить вывод</h2>

            <div className="mb-3">
              <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.65)]">
                Сумма (₽)
              </label>
              <input
                type="number"
                min="1"
                step="0.01"
                value={withdrawAmount}
                onChange={(e) => setWithdrawAmount(e.target.value)}
                placeholder="0.00"
                className="h-10 w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 text-[14px] text-[#0d0d0d] outline-none focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] transition-all"
              />
            </div>

            <div className="mb-4">
              <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.65)]">
                Номер карты
              </label>
              <input
                type="text"
                value={withdrawCard}
                onChange={(e) => setWithdrawCard(e.target.value)}
                placeholder="0000 0000 0000 0000"
                maxLength={19}
                className="h-10 w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 text-[14px] text-[#0d0d0d] outline-none focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] transition-all"
              />
            </div>

            {withdrawError && (
              <div className="mb-3 rounded-[8px] bg-[rgba(231,76,60,0.08)] px-3 py-2.5 text-[13px] text-[#e74c3c]">
                {withdrawError}
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => setShowWithdrawModal(false)}
                className="flex-1 h-10 rounded-[8px] border border-[rgba(13,13,13,0.12)] text-[14px] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={() => withdrawMutation.mutate()}
                disabled={
                  withdrawMutation.isPending ||
                  !withdrawAmount ||
                  !withdrawCard ||
                  parseFloat(withdrawAmount) <= 0
                }
                className="flex-1 h-10 rounded-[8px] bg-[#0a7cff] text-[14px] font-medium text-white hover:bg-[#0066cc] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {withdrawMutation.isPending ? "Отправка..." : "Запросить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
