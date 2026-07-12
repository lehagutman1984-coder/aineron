"use client";

import { useState } from "react";
import { Link } from "@/i18n/navigation";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CreditCard,
  Wallet,
  History,
  Tag,
  ChevronRight,
  CheckCircle,
  Clock,
  XCircle,
  RefreshCw,
  AlertCircle,
  X,
  Star,
  Bitcoin,
  ExternalLink,
} from "lucide-react";
import {
  getTariffs,
  payTariff,
  getPageSaleSettings,
  buyPages,
  getPaymentHistory,
  applyPromoCode,
  checkPromoCode,
  updateAutoRenew,
  getCryptoConfig,
  createCryptoTopup,
  getCryptoTopupStatus,
} from "@/lib/api/client";
import type { CryptoTopupResponse } from "@/lib/api/client";
import type { PromoCheckResponse } from "@/lib/api/client";
import type { Tariff, PaymentHistory, RobokassaForm, UserSubscription } from "@/lib/api/types";
import { formatMoney, rubToKopecks, CURRENCY } from "@/lib/money";
import { useTranslations } from "next-intl";
import { useAuthStore } from "@/lib/stores/auth";

// ── Robokassa redirect ───────────────────────────────────────────────────────

function submitRobokassaForm(form: RobokassaForm) {
  const f = document.createElement("form");
  f.method = form.method;
  f.action = form.action;
  Object.entries(form.fields).forEach(([name, value]) => {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    f.appendChild(input);
  });
  document.body.appendChild(f);
  f.submit();
}

// ── Purchase confirmation modal (условия Робокассы) ─────────────────────────

export interface PurchaseInfo {
  mode: "subscription" | "topup";
  title: string;
  amount: number; // руб
}

function ConfirmPurchaseModal({
  purchase,
  tariffId,
  loading,
  onConfirm,
  onClose,
}: {
  purchase: PurchaseInfo;
  tariffId?: number;
  loading: boolean;
  onConfirm: (promoCode?: string) => void;
  onClose: () => void;
}) {
  const [agreed, setAgreed] = useState(false);
  const isSub = purchase.mode === "subscription";

  // Скидочный промокод (только для тарифов)
  const [promoInput, setPromoInput] = useState("");
  const [promoApplied, setPromoApplied] = useState<PromoCheckResponse | null>(null);
  const [promoError, setPromoError] = useState<string | null>(null);
  const [promoChecking, setPromoChecking] = useState(false);

  async function handleCheckPromo() {
    if (!promoInput.trim() || !tariffId) return;
    setPromoChecking(true);
    setPromoError(null);
    try {
      const result = await checkPromoCode(promoInput.trim(), tariffId);
      if (result.type === "balance") {
        setPromoError(
          `Этот промокод начисляет ${formatMoney(result.kopecks)} на баланс — примените его в разделе «Промокод»`,
        );
      } else {
        setPromoApplied(result);
      }
    } catch (err) {
      setPromoError((err as Error).message);
    } finally {
      setPromoChecking(false);
    }
  }

  const effectiveAmount = promoApplied?.discounted_price
    ? parseFloat(promoApplied.discounted_price)
    : purchase.amount;
  const amountLabel = effectiveAmount.toLocaleString("ru-RU");
  const fullAmountLabel = purchase.amount.toLocaleString("ru-RU");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-[16px] bg-[var(--card-bg)] border border-[var(--color-border)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <h3 className="text-xl font-bold text-[var(--color-text-primary)]">
            Подтверждение покупки
          </h3>
          <button
            onClick={onClose}
            className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
            aria-label="Закрыть"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--color-border)]">
            <Star size={16} className="text-[var(--color-accent)]" />
          </div>
          <div>
            <p className="font-semibold text-[var(--color-text-primary)]">{purchase.title}</p>
            <p className="text-sm text-[var(--color-text-secondary)]">
              {isSub ? "Ежемесячная подписка с автопродлением" : "Разовое пополнение баланса"}
            </p>
          </div>
        </div>

        <div className="space-y-2 text-sm mb-4">
          <div className="flex items-center justify-between">
            <span className="text-[var(--color-text-secondary)]">
              {isSub ? "Стоимость тарифа" : "Сумма пополнения"}
            </span>
            <span className="text-[var(--color-text-primary)]">
              {fullAmountLabel} ₽{isSub && " / мес"}
            </span>
          </div>
          {promoApplied && (
            <div className="flex items-center justify-between">
              <span className="text-[var(--color-text-secondary)]">
                Промокод {promoApplied.code}
              </span>
              <span className="text-green-600 font-medium">
                −{promoApplied.discount_percent}%
              </span>
            </div>
          )}
          <div className="flex items-center justify-between">
            <span className="text-[var(--color-text-secondary)]">Способ оплаты</span>
            <span className="text-[var(--color-text-primary)]">Банковская карта</span>
          </div>
          <div className="flex items-center justify-between font-semibold">
            <span className="text-[var(--color-text-primary)]">Итого к оплате</span>
            <span className="text-[var(--color-text-primary)]">
              {promoApplied && (
                <span className="me-2 font-normal text-[var(--color-text-secondary)] line-through">
                  {fullAmountLabel} ₽
                </span>
              )}
              {amountLabel} ₽
            </span>
          </div>
        </div>

        {isSub && tariffId && (
          <div className="mb-4">
            {promoApplied ? (
              <p className="flex items-center justify-between gap-2 rounded-lg bg-green-500/8 border border-green-500/20 px-3 py-2 text-sm text-green-700">
                <span className="flex items-center gap-1.5 min-w-0">
                  <CheckCircle size={14} className="shrink-0" />
                  <span className="truncate">Скидка {promoApplied.discount_percent}% применена</span>
                </span>
                <button
                  onClick={() => {
                    setPromoApplied(null);
                    setPromoInput("");
                  }}
                  className="shrink-0 text-xs underline hover:no-underline"
                >
                  Убрать
                </button>
              </p>
            ) : (
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Промокод на скидку"
                  value={promoInput}
                  onChange={(e) => {
                    setPromoInput(e.target.value.toUpperCase());
                    setPromoError(null);
                  }}
                  className="flex-1 min-w-0 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]
                    px-3 py-2 text-sm text-[var(--color-text-primary)] focus:outline-none
                    focus:border-[var(--color-accent)]"
                />
                <button
                  onClick={handleCheckPromo}
                  disabled={!promoInput.trim() || promoChecking}
                  className="shrink-0 px-3 py-2 rounded-lg text-sm font-medium border border-[var(--color-border)]
                    text-[var(--color-text-primary)] hover:bg-[var(--color-bg)] transition-colors
                    disabled:opacity-40"
                >
                  {promoChecking ? "..." : "Применить"}
                </button>
              </div>
            )}
            {promoError && (
              <p className="mt-2 text-xs text-red-500 flex items-start gap-1.5">
                <AlertCircle size={13} className="shrink-0 mt-0.5" /> {promoError}
              </p>
            )}
          </div>
        )}

        {isSub && (
          <p className="mb-4 text-xs leading-relaxed text-[var(--color-text-secondary)]">
            {promoApplied
              ? `Оплачивая, вы соглашаетесь на автоматическое продление подписки: первый платёж ${amountLabel} ₽ со скидкой, далее ежемесячно ${fullAmountLabel} ₽ с вашей банковской карты до отмены подписки. Отменить подписку можно в любой момент в личном кабинете — раздел «Тарифы и платежи».`
              : `Оплачивая, вы соглашаетесь на ежемесячное автоматическое списание ${amountLabel} ₽ с вашей банковской карты до отмены подписки. Отменить подписку можно в любой момент в личном кабинете — раздел «Тарифы и платежи».`}
          </p>
        )}

        <label className="flex items-start gap-2.5 mb-5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--color-accent)]"
          />
          <span className="text-sm text-[var(--color-text-primary)]">
            Я согласен с{" "}
            <Link href="/terms/" target="_blank" className="underline hover:text-[var(--color-accent)]">
              условиями использования
            </Link>{" "}
            и{" "}
            <Link href="/privacy-policy/" target="_blank" className="underline hover:text-[var(--color-accent)]">
              политикой конфиденциальности
            </Link>
          </span>
        </label>

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-lg text-sm font-medium border border-[var(--color-border)]
              text-[var(--color-text-primary)] hover:bg-[var(--color-bg)] transition-colors"
          >
            Отмена
          </button>
          <button
            onClick={() => onConfirm(promoApplied?.code)}
            disabled={!agreed || loading}
            className="flex-1 py-2.5 rounded-lg text-sm font-medium bg-[var(--color-accent)] text-white
              hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? "Перенаправление..." : `Оплатить ${amountLabel} ₽`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function paymentStatusIcon(status: PaymentHistory["status"]) {
  switch (status) {
    case "success":
      return <CheckCircle size={16} className="text-green-500" />;
    case "pending":
      return <Clock size={16} className="text-yellow-500" />;
    case "failed":
      return <XCircle size={16} className="text-red-500" />;
    case "refunded":
      return <RefreshCw size={16} className="text-blue-500" />;
  }
}

function paymentStatusLabel(status: PaymentHistory["status"], t: (k: string) => string) {
  const map: Record<PaymentHistory["status"], string> = {
    success: t("statusSuccess"),
    pending: t("statusPending"),
    failed: t("statusFailed"),
    refunded: t("statusRefunded"),
  };
  return map[status];
}

function paymentTypeLabel(type: PaymentHistory["payment_type"], t: (k: string) => string) {
  const map: Record<PaymentHistory["payment_type"], string> = {
    subscription: t("typeSubscription"),
    pages: t("typePages"),
    promo: t("typePromo"),
  };
  return map[type];
}

// ── Section header ────────────────────────────────────────────────────────────

function SectionHeader({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <Icon size={20} className="text-[var(--color-accent)]" />
      <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">{title}</h2>
    </div>
  );
}

// ── Subscription management (автопродление / отмена) ────────────────────────

function SubscriptionSection({ subscription }: { subscription: UserSubscription }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (autoRenew: boolean) => updateAutoRenew(autoRenew),
    onSuccess: (data) => {
      setMessage(data.message);
      queryClient.invalidateQueries({ queryKey: ["tariffs"] });
    },
  });

  const nextCharge = subscription.next_payment_date ?? subscription.expires_at;

  return (
    <section>
      <SectionHeader icon={RefreshCw} title="Тарифный план" />
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[var(--color-border)]">
              <Star size={16} className="text-[var(--color-accent)]" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="font-semibold text-[var(--color-text-primary)]">
                  {subscription.tariff.display_name}
                </p>
                {subscription.auto_renew ? (
                  <span className="text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-green-500/10 text-green-600">
                    Автопродление
                  </span>
                ) : (
                  <span className="text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600">
                    Отменено
                  </span>
                )}
              </div>
              <p className="text-sm text-[var(--color-text-secondary)] mt-0.5">
                {subscription.auto_renew
                  ? `Следующее списание: ${formatDate(nextCharge)}`
                  : `Активен до: ${formatDate(subscription.expires_at)}`}
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              setMessage(null);
              mutation.mutate(!subscription.auto_renew);
            }}
            disabled={mutation.isPending}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
              subscription.auto_renew
                ? "border border-[var(--color-border)] text-[var(--color-text-primary)] hover:border-red-400 hover:text-red-500"
                : "bg-[var(--color-accent)] text-white hover:opacity-90"
            }`}
          >
            {mutation.isPending
              ? "..."
              : subscription.auto_renew
                ? "Отменить подписку"
                : "Возобновить"}
          </button>
        </div>

        {!subscription.auto_renew && (
          <p className="flex items-center gap-2 rounded-lg bg-green-500/8 border border-green-500/20 px-3 py-2.5 text-sm text-green-700">
            <CheckCircle size={14} className="shrink-0" />
            Автопродление отключено. Тариф будет активен до конца оплаченного периода.
          </p>
        )}

        {message && subscription.auto_renew && (
          <p className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
            <CheckCircle size={14} className="text-green-500 shrink-0" />
            {message}
          </p>
        )}

        {mutation.error && (
          <p className="flex items-center gap-2 text-sm text-red-500">
            <AlertCircle size={14} className="shrink-0" />
            {(mutation.error as Error).message}
          </p>
        )}

        <p className="text-xs text-[var(--color-text-secondary)]">
          При включённом автопродлении подписка продлевается автоматически каждый месяц.
          Средства списываются за 3 дня до окончания оплаченного периода.
        </p>
      </div>
    </section>
  );
}

// ── Tariff cards ─────────────────────────────────────────────────────────────

function TariffCard({
  tariff,
  isActive,
  onPay,
  loading,
}: {
  tariff: Tariff;
  isActive: boolean;
  onPay: (id: number) => void;
  loading: boolean;
}) {
  return (
    <div
      className={`relative rounded-xl border p-5 flex flex-col gap-3 transition-colors ${
        isActive
          ? "border-[var(--color-accent)] bg-[var(--color-accent)]/5"
          : "border-[var(--color-border)] bg-[var(--color-surface)]"
      }`}
    >
      {isActive && (
        <span className="absolute top-3 right-3 text-xs font-medium px-2 py-0.5 rounded-full bg-[var(--color-accent)] text-white">
          Текущий
        </span>
      )}
      <p className="font-semibold text-[var(--color-text-primary)]">{tariff.display_name}</p>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-bold text-[var(--color-text-primary)]">
          {tariff.is_free ? "Бесплатно" : `${parseFloat(tariff.price).toLocaleString("ru-RU")} ₽`}
        </span>
        {!tariff.is_free && tariff.duration_days < 36500 && (
          <span className="text-sm text-[var(--color-text-secondary)]">
            / {tariff.duration_days} дней
          </span>
        )}
      </div>
      <p className="text-sm text-[var(--color-text-primary)]">
        На баланс: <span className="font-medium">{formatMoney(tariff.balance_grant_kopecks)}</span>
        {(() => {
          const priceRub = parseFloat(tariff.price);
          const grantRub = tariff.balance_grant_kopecks / 100;
          if (tariff.is_free || priceRub <= 0 || grantRub <= priceRub) return null;
          const pct = Math.round(((grantRub - priceRub) / priceRub) * 100);
          return (
            <span className="ms-1.5 text-xs font-medium px-1.5 py-0.5 rounded bg-[var(--color-accent)]/10 text-[var(--color-accent)]">
              +{pct}% бонус
            </span>
          );
        })()}
      </p>
      {tariff.description && (
        <p className="text-xs leading-relaxed text-[var(--color-text-secondary)]">
          {tariff.description}
        </p>
      )}
      {!tariff.is_free && (
        <button
          onClick={() => onPay(tariff.id)}
          disabled={loading || isActive}
          className="mt-auto w-full py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50
            bg-[var(--color-accent)] text-white hover:opacity-90 disabled:cursor-not-allowed"
        >
          {loading ? "Перенаправление..." : isActive ? "Активен" : "Купить"}
        </button>
      )}
    </div>
  );
}

// ── Stars slider ─────────────────────────────────────────────────────────────

function StarsSection() {
  const queryClient = useQueryClient();
  const { data: settings, isLoading } = useQuery({
    queryKey: ["page-sale-settings"],
    queryFn: getPageSaleSettings,
  });
  const [count, setCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const mutation = useMutation({
    mutationFn: buyPages,
    onSuccess: (data) => {
      submitRobokassaForm(data.form);
    },
    onError: (err: Error) => {
      setError(err.message);
      setConfirmOpen(false);
    },
  });

  if (isLoading || !settings) {
    return <div className="text-[var(--color-text-secondary)] text-sm">Загрузка...</div>;
  }

  if (!settings.is_active) {
    return (
      <p className="text-[var(--color-text-secondary)] text-sm">
        Пополнение баланса временно недоступно.
      </p>
    );
  }

  const price = parseFloat(settings.price_per_page);
  const total = (price * count).toFixed(2);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm text-[var(--color-text-secondary)]">
        <span>1 ₽ на балансе = {price.toLocaleString("ru-RU")} ₽</span>
        <span>
          Мин: {settings.min_pages_for_purchase} — Макс: {settings.max_pages_for_purchase}
        </span>
      </div>
      <input
        type="range"
        min={settings.min_pages_for_purchase}
        max={settings.max_pages_for_purchase}
        step={1}
        value={count || settings.min_pages_for_purchase}
        onChange={(e) => {
          setCount(parseInt(e.target.value));
          setError(null);
        }}
        className="w-full accent-[var(--color-accent)]"
      />
      <div className="flex items-center justify-between">
        <p className="text-[var(--color-text-primary)] font-medium">
          Пополнение на {count || settings.min_pages_for_purchase} ₽ ={" "}
          <span className="font-bold">{parseFloat(total).toLocaleString("ru-RU")} ₽</span>
        </p>
        <button
          onClick={() => {
            setError(null);
            setConfirmOpen(true);
          }}
          disabled={mutation.isPending}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--color-accent)] text-white
            hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {mutation.isPending ? "Перенаправление..." : "Купить"}
        </button>
      </div>
      {error && (
        <p className="text-red-500 text-sm flex items-center gap-1.5">
          <AlertCircle size={14} /> {error}
        </p>
      )}
      {confirmOpen && (
        <ConfirmPurchaseModal
          purchase={{
            mode: "topup",
            title: "Пополнение баланса",
            amount: parseFloat(total),
          }}
          loading={mutation.isPending}
          onConfirm={() => mutation.mutate(count || settings.min_pages_for_purchase)}
          onClose={() => {
            if (!mutation.isPending) setConfirmOpen(false);
          }}
        />
      )}
    </div>
  );
}

// ── Crypto payment (Crypto Pay / @CryptoBot) ─────────────────────────────────

function CryptoSection() {
  const queryClient = useQueryClient();
  const setBalance = useAuthStore((s) => s.setBalance);

  const { data: config } = useQuery({
    queryKey: ["crypto-config"],
    queryFn: getCryptoConfig,
  });

  const [amount, setAmount] = useState<number | null>(null);
  const [invoice, setInvoice] = useState<CryptoTopupResponse | null>(null);
  const [paid, setPaid] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createCryptoTopup,
    onSuccess: (data) => {
      setInvoice(data);
      setPaid(false);
      window.open(data.pay_url, "_blank", "noopener");
    },
    onError: (err: Error) => setError(err.message),
  });

  // Поллинг статуса, пока счёт не оплачен/не истёк
  useQuery({
    queryKey: ["crypto-status", invoice?.payment_id],
    queryFn: async () => {
      const status = await getCryptoTopupStatus(invoice!.payment_id);
      if (status.status === "success") {
        setPaid(true);
        setInvoice(null);
        setBalance(status.balance_kopecks);
        queryClient.invalidateQueries({ queryKey: ["tariffs"] });
        queryClient.invalidateQueries({ queryKey: ["payment-history"] });
      } else if (status.status === "failed") {
        setInvoice(null);
        setError(
          config?.mode === "usd"
            ? "The invoice expired or was cancelled. Create a new one."
            : "Счёт истёк или отменён. Создайте новый.",
        );
      }
      return status;
    },
    enabled: invoice !== null,
    refetchInterval: 5000,
  });

  // Канал выключен на бэкенде (CRYPTO_PAY_ENABLED=0) — блок скрыт целиком
  if (!config?.enabled) return null;

  const isUsd = config.mode === "usd";
  const value = amount ?? config.min_amount;
  // Локализация блока: usd-режим = международный инстанс (английский),
  // rub-режим = aineron.ru (русский). До полного i18n-извлечения (G2).
  const L = isUsd
    ? {
        title: "Pay with crypto",
        intro: `Top up your balance with ${config.assets.join(", ")} via @CryptoBot. Invoice is issued in USD.`,
        waiting: (a: string) => `Waiting for payment of $${a}...`,
        open: "Open invoice",
        cancel: "Cancel",
        note: "The invoice is valid for 30 minutes. Your balance updates automatically after payment.",
        label: `Amount, $ (${config.min_amount}–${config.max_amount})`,
        pay: "Create invoice",
        creating: "Creating invoice...",
        paid: "Payment received — balance updated.",
        failed: "The invoice expired or was cancelled. Create a new one.",
        receive: (c: number) => `You will receive ${c.toLocaleString("en-US")} credits`,
      }
    : {
        title: "Оплата криптовалютой",
        intro: `Пополнение баланса через ${config.assets.join(", ")} — счёт выставляется в @CryptoBot, зачисление в рублях по номиналу счёта.`,
        waiting: (a: string) => `Ожидаем оплату счёта на ${parseFloat(a).toLocaleString("ru-RU")} ₽...`,
        open: "Открыть счёт",
        cancel: "Отмена",
        note: "Счёт действителен 30 минут. Баланс пополнится автоматически после оплаты.",
        label: `Сумма, ₽ (от ${config.min_amount} до ${config.max_amount})`,
        pay: "Выставить счёт",
        creating: "Создание счёта...",
        paid: "Оплата получена, баланс пополнен.",
        failed: "Счёт истёк или отменён. Создайте новый.",
        receive: () => "",
      };

  const USD_PACKAGES = [5, 10, 25, 50];

  return (
    <section>
      <SectionHeader icon={Bitcoin} title={L.title} />
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
        <p className="text-sm text-[var(--color-text-secondary)]">{L.intro}</p>

        {invoice ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-[var(--color-text-primary)]">
              <Clock size={16} className="text-yellow-500 shrink-0 animate-pulse" />
              {L.waiting(invoice.amount)}
            </div>
            <div className="flex flex-wrap gap-3">
              <a
                href={invoice.pay_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium
                  bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
              >
                {L.open} <ExternalLink size={14} />
              </a>
              <button
                onClick={() => setInvoice(null)}
                className="px-4 py-2 rounded-lg text-sm font-medium border border-[var(--color-border)]
                  text-[var(--color-text-primary)] hover:bg-[var(--color-bg)] transition-colors"
              >
                {L.cancel}
              </button>
            </div>
            <p className="text-xs text-[var(--color-text-secondary)]">{L.note}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {isUsd && (
              <div className="flex flex-wrap gap-2">
                {USD_PACKAGES.map((usd) => (
                  <button
                    key={usd}
                    onClick={() => {
                      setAmount(usd);
                      setError(null);
                    }}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                      value === usd
                        ? "border-[var(--color-accent)] text-[var(--color-accent)] bg-[var(--color-accent)]/5"
                        : "border-[var(--color-border)] text-[var(--color-text-primary)] hover:border-[var(--color-accent)]"
                    }`}
                  >
                    ${usd}
                  </button>
                ))}
              </div>
            )}
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex-1 min-w-[160px]">
                <label className="block text-xs text-[var(--color-text-secondary)] mb-1.5">
                  {L.label}
                </label>
                <input
                  type="number"
                  min={config.min_amount}
                  max={config.max_amount}
                  value={value}
                  onChange={(e) => {
                    setAmount(parseInt(e.target.value) || 0);
                    setError(null);
                  }}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]
                    px-3 py-2 text-sm text-[var(--color-text-primary)] focus:outline-none
                    focus:border-[var(--color-accent)]"
                />
              </div>
              <button
                onClick={() => {
                  setError(null);
                  setPaid(false);
                  mutation.mutate(isUsd ? { amount_usd: value } : { amount: value });
                }}
                disabled={
                  mutation.isPending || value < config.min_amount || value > config.max_amount
                }
                className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--color-accent)] text-white
                  hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {mutation.isPending ? L.creating : L.pay}
              </button>
            </div>
            {isUsd && config.kopecks_per_usd && value >= config.min_amount && (
              <p className="text-xs text-[var(--color-text-secondary)]">
                {L.receive(value * config.kopecks_per_usd)}
              </p>
            )}
          </div>
        )}

        {paid && (
          <p className="text-green-500 text-sm flex items-center gap-1.5">
            <CheckCircle size={14} /> {L.paid}
          </p>
        )}
        {error && (
          <p className="text-red-500 text-sm flex items-center gap-1.5">
            <AlertCircle size={14} /> {error}
          </p>
        )}
      </div>
    </section>
  );
}

// ── Promo code form ───────────────────────────────────────────────────────────

function PromoSection() {
  const t = useTranslations("billing");
  const queryClient = useQueryClient();
  const setBalance = useAuthStore((s) => s.setBalance);
  const [code, setCode] = useState("");
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => applyPromoCode(code),
    onSuccess: (data) => {
      setSuccessMsg(data.message);
      setCode("");
      if (data.new_balance_kopecks != null) {
        setBalance(data.new_balance_kopecks);
      }
      queryClient.invalidateQueries({ queryKey: ["payment-history"] });
      queryClient.invalidateQueries({ queryKey: ["tariffs"] });
    },
  });

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          type="text"
          placeholder={t("promoPlaceholder")}
          value={code}
          onChange={(e) => {
            setCode(e.target.value.toUpperCase());
            setSuccessMsg(null);
          }}
          className="flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]
            px-3 py-2 text-sm text-[var(--color-text-primary)] focus:outline-none
            focus:border-[var(--color-accent)]"
        />
        <button
          onClick={() => mutation.mutate()}
          disabled={!code.trim() || mutation.isPending}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--color-accent)] text-white
            hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {mutation.isPending ? "..." : t("promoApply")}
        </button>
      </div>
      {mutation.error && (
        <p className="text-red-500 text-sm flex items-center gap-1.5">
          <AlertCircle size={14} /> {(mutation.error as Error).message}
        </p>
      )}
      {successMsg && (
        <p className="text-green-500 text-sm flex items-center gap-1.5">
          <CheckCircle size={14} /> {successMsg}
        </p>
      )}
    </div>
  );
}

// ── Payment history ───────────────────────────────────────────────────────────

function HistorySection() {
  const t = useTranslations("billing");
  const { data: payments, isLoading } = useQuery({
    queryKey: ["payment-history"],
    queryFn: getPaymentHistory,
  });

  if (isLoading) {
    return <div className="text-[var(--color-text-secondary)] text-sm">{t("loading")}</div>;
  }

  if (!payments?.length) {
    return (
      <p className="text-[var(--color-text-secondary)] text-sm">
        {t("historyEmpty")}
      </p>
    );
  }

  return (
    <div className="divide-y divide-[var(--color-border)]">
      {payments.map((p) => (
        <div key={p.id} className="flex items-center justify-between py-3 gap-4">
          <div className="flex items-center gap-3 min-w-0">
            {paymentStatusIcon(p.status)}
            <div className="min-w-0">
              <p className="text-sm font-medium text-[var(--color-text-primary)] truncate">
                {p.description || paymentTypeLabel(p.payment_type, t)}
              </p>
              <p className="text-xs text-[var(--color-text-secondary)]">
                {formatDate(p.created_at)} · {paymentTypeLabel(p.payment_type, t)}
              </p>
            </div>
          </div>
          <div className="text-end shrink-0">
            {parseFloat(p.amount) > 0 && (
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                {formatMoney(rubToKopecks(parseFloat(p.amount)))}
              </p>
            )}
            <p className="text-xs text-[var(--color-text-secondary)]">
              {p.amount_kopecks != null
                ? `+${formatMoney(p.amount_kopecks)}`
                : `+${formatMoney(rubToKopecks(p.pages_count))}`}{" "}
              · {paymentStatusLabel(p.status, t)}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function BillingPage() {
  const queryClient = useQueryClient();
  const {
    data: tariffsData,
    isLoading: tariffsLoading,
    error: tariffsError,
  } = useQuery({
    queryKey: ["tariffs"],
    queryFn: getTariffs,
  });

  const [payLoading, setPayLoading] = useState<number | null>(null);
  const [payError, setPayError] = useState<string | null>(null);
  const [pendingTariff, setPendingTariff] = useState<Tariff | null>(null);

  async function handlePay(tariffId: number, promoCode?: string) {
    setPayLoading(tariffId);
    setPayError(null);
    try {
      const data = await payTariff(tariffId, promoCode);
      submitRobokassaForm(data.form);
    } catch (err) {
      setPayError((err as Error).message);
      setPayLoading(null);
      setPendingTariff(null);
    }
  }

  const activeTariffId = tariffsData?.current_subscription?.tariff?.id ?? null;
  const currentSubscription = tariffsData?.current_subscription ?? null;
  const showSubscription =
    currentSubscription && currentSubscription.is_active && !currentSubscription.tariff.is_free;
  // Кредитная витрина (международный инстанс): тарифы, Robokassa и подписки скрыты,
  // остаются крипто-пополнение, промокоды и история.
  const isCredits = CURRENCY === "credits";

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-10">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">
          {isCredits ? "Balance & billing" : "Баланс и тарифы"}
        </h1>
        {tariffsData && (
          <p className="mt-1 text-[var(--color-text-secondary)]">
            {isCredits ? "Current balance: " : "Текущий баланс: "}
            <span className="font-semibold text-[var(--color-text-primary)]">
              {formatMoney(tariffsData.balance_kopecks)}
            </span>
            {!isCredits && tariffsData.current_subscription && (
              <>
                {" "}
                · Подписка до{" "}
                <span className="font-semibold text-[var(--color-text-primary)]">
                  {formatDate(tariffsData.current_subscription.expires_at)}
                </span>
              </>
            )}
          </p>
        )}
      </div>

      {/* Subscription management */}
      {!isCredits && showSubscription && <SubscriptionSection subscription={currentSubscription} />}

      {/* Tariffs */}
      {!isCredits && (
      <section>
        <SectionHeader icon={CreditCard} title="Тарифы" />
        <p className="text-sm text-[var(--color-text-secondary)] mb-4 -mt-2">
          Тариф — это пополнение баланса с бонусом и подписка на 30 дней.
          Баланс не сгорает: 30 дней — период продления подписки, неистраченный
          остаток сохраняется. Все модели доступны на любом тарифе.
        </p>
        {tariffsLoading && (
          <p className="text-[var(--color-text-secondary)] text-sm">Загрузка...</p>
        )}
        {tariffsError && (
          <p className="text-red-500 text-sm">Не удалось загрузить тарифы.</p>
        )}
        {payError && (
          <p className="text-red-500 text-sm mb-3 flex items-center gap-1.5">
            <AlertCircle size={14} /> {payError}
          </p>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {tariffsData?.tariffs
            .filter((t) => !t.is_free)
            .map((t) => (
              <TariffCard
                key={t.id}
                tariff={t}
                isActive={t.id === activeTariffId}
                onPay={() => {
                  setPayError(null);
                  setPendingTariff(t);
                }}
                loading={payLoading === t.id}
              />
            ))}
        </div>
      </section>
      )}

      {/* Buy stars (Robokassa — только rub-витрина) */}
      {!isCredits && (
      <section>
        <SectionHeader icon={Wallet} title="Пополнить баланс" />
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <StarsSection />
        </div>
      </section>
      )}

      {/* Crypto payment (скрыт при CRYPTO_PAY_ENABLED=0) */}
      <CryptoSection />

      {/* Promo code */}
      <section>
        <SectionHeader icon={Tag} title={isCredits ? "Promo code" : "Промокод"} />
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <PromoSection />
        </div>
      </section>

      {/* Payment history */}
      <section>
        <SectionHeader icon={History} title={isCredits ? "Payment history" : "История платежей"} />
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-5">
          <HistorySection />
        </div>
      </section>

      {/* Purchase confirmation modal (условия Робокассы) */}
      {pendingTariff && (
        <ConfirmPurchaseModal
          purchase={{
            mode: "subscription",
            title: pendingTariff.display_name,
            amount: parseFloat(pendingTariff.price),
          }}
          tariffId={pendingTariff.id}
          loading={payLoading === pendingTariff.id}
          onConfirm={(promoCode) => handlePay(pendingTariff.id, promoCode)}
          onClose={() => {
            if (payLoading === null) setPendingTariff(null);
          }}
        />
      )}
    </div>
  );
}
