"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CreditCard,
  Star,
  History,
  Tag,
  ChevronRight,
  CheckCircle,
  Clock,
  XCircle,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import {
  getTariffs,
  payTariff,
  getPageSaleSettings,
  buyPages,
  getPaymentHistory,
  applyPromoCode,
} from "@/lib/api/client";
import type { Tariff, PaymentHistory, RobokassaForm } from "@/lib/api/types";

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

function paymentStatusLabel(status: PaymentHistory["status"]) {
  const map: Record<PaymentHistory["status"], string> = {
    success: "Оплачено",
    pending: "Ожидает",
    failed: "Ошибка",
    refunded: "Возврат",
  };
  return map[status];
}

function paymentTypeLabel(type: PaymentHistory["payment_type"]) {
  const map: Record<PaymentHistory["payment_type"], string> = {
    subscription: "Тариф",
    pages: "Звёзды",
    promo: "Промокод",
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
      <div>
        <p className="font-semibold text-[var(--color-text-primary)]">{tariff.display_name}</p>
        <p className="text-sm text-[var(--color-text-secondary)] mt-0.5">
          {tariff.pages_count} звёзд
          {tariff.duration_days < 36500 && ` · ${tariff.duration_days} дней`}
        </p>
      </div>
      <p className="text-2xl font-bold text-[var(--color-text-primary)]">
        {tariff.is_free ? "Бесплатно" : `${parseFloat(tariff.price).toLocaleString("ru-RU")} ₽`}
      </p>
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

  const mutation = useMutation({
    mutationFn: buyPages,
    onSuccess: (data) => {
      submitRobokassaForm(data.form);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  if (isLoading || !settings) {
    return <div className="text-[var(--color-text-secondary)] text-sm">Загрузка...</div>;
  }

  if (!settings.is_active) {
    return (
      <p className="text-[var(--color-text-secondary)] text-sm">
        Покупка звёзд временно недоступна.
      </p>
    );
  }

  const price = parseFloat(settings.price_per_page);
  const total = (price * count).toFixed(2);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm text-[var(--color-text-secondary)]">
        <span>Цена: {price.toLocaleString("ru-RU")} ₽ / звезда</span>
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
          {count || settings.min_pages_for_purchase} звёзд ={" "}
          <span className="font-bold">{parseFloat(total).toLocaleString("ru-RU")} ₽</span>
        </p>
        <button
          onClick={() => {
            setError(null);
            mutation.mutate(count || settings.min_pages_for_purchase);
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
    </div>
  );
}

// ── Promo code form ───────────────────────────────────────────────────────────

function PromoSection() {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => applyPromoCode(code),
    onSuccess: (data) => {
      setSuccessMsg(data.message);
      setCode("");
      queryClient.invalidateQueries({ queryKey: ["payment-history"] });
      queryClient.invalidateQueries({ queryKey: ["tariffs"] });
    },
  });

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Введите промокод"
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
          {mutation.isPending ? "..." : "Применить"}
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
  const { data: payments, isLoading } = useQuery({
    queryKey: ["payment-history"],
    queryFn: getPaymentHistory,
  });

  if (isLoading) {
    return <div className="text-[var(--color-text-secondary)] text-sm">Загрузка...</div>;
  }

  if (!payments?.length) {
    return (
      <p className="text-[var(--color-text-secondary)] text-sm">
        История платежей пуста.
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
                {p.description || paymentTypeLabel(p.payment_type)}
              </p>
              <p className="text-xs text-[var(--color-text-secondary)]">
                {formatDate(p.created_at)} · {paymentTypeLabel(p.payment_type)}
              </p>
            </div>
          </div>
          <div className="text-right shrink-0">
            {parseFloat(p.amount) > 0 && (
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                {parseFloat(p.amount).toLocaleString("ru-RU")} ₽
              </p>
            )}
            <p className="text-xs text-[var(--color-text-secondary)]">
              +{p.pages_count} зв. · {paymentStatusLabel(p.status)}
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

  async function handlePay(tariffId: number) {
    setPayLoading(tariffId);
    setPayError(null);
    try {
      const data = await payTariff(tariffId);
      submitRobokassaForm(data.form);
    } catch (err) {
      setPayError((err as Error).message);
      setPayLoading(null);
    }
  }

  const activeTariffId = tariffsData?.current_subscription?.tariff?.id ?? null;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-10">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Баланс и тарифы</h1>
        {tariffsData && (
          <p className="mt-1 text-[var(--color-text-secondary)]">
            Текущий баланс:{" "}
            <span className="font-semibold text-[var(--color-text-primary)]">
              {tariffsData.pages_count} звёзд
            </span>
            {tariffsData.current_subscription && (
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

      {/* Tariffs */}
      <section>
        <SectionHeader icon={CreditCard} title="Тарифы" />
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
                onPay={handlePay}
                loading={payLoading === t.id}
              />
            ))}
        </div>
      </section>

      {/* Buy stars */}
      <section>
        <SectionHeader icon={Star} title="Купить звёзды" />
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <StarsSection />
        </div>
      </section>

      {/* Promo code */}
      <section>
        <SectionHeader icon={Tag} title="Промокод" />
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <PromoSection />
        </div>
      </section>

      {/* Payment history */}
      <section>
        <SectionHeader icon={History} title="История платежей" />
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-5">
          <HistorySection />
        </div>
      </section>
    </div>
  );
}
