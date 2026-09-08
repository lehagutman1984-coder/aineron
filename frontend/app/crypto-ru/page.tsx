import type { Metadata } from "next";
import { Coins, ArrowRight, ArrowLeft } from "lucide-react";

export const metadata: Metadata = {
  title: "Оплата криптовалютой — aineron",
  description: "Оплата криптовалютой доступна на международной версии aineron.",
  robots: { index: false, follow: false },
};

export default function CryptoRuBridgePage() {
  return (
    <main
      className="min-h-screen flex items-center justify-center p-6"
      style={{ background: "var(--color-bg)", color: "var(--color-text-primary)" }}
    >
      <div
        className="w-full max-w-md rounded-2xl p-8 space-y-6"
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
        }}
      >
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center"
          style={{ background: "var(--color-accent)" }}
        >
          <Coins size={22} color="#fff" />
        </div>

        <div className="space-y-2">
          <h1 className="text-xl font-semibold">Оплата криптовалютой</h1>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            На aineron.ru пополнение баланса доступно в рублях (банковской картой).
            Если вам нужна оплата криптовалютой (USDT, TON и другими) — она есть
            на международной версии сервиса, aineron.net. Каталог моделей и
            функциональность там те же самые.
          </p>
        </div>

        <a
          href="https://aineron.net/account/billing"
          className="flex items-center justify-center gap-2 w-full rounded-lg px-4 py-3 text-sm font-medium transition-opacity hover:opacity-90"
          style={{ background: "var(--color-accent)", color: "#fff" }}
        >
          Перейти на aineron.net <ArrowRight size={16} />
        </a>

        <a
          href="https://aineron.ru/"
          className="flex items-center justify-center gap-1.5 text-sm hover:underline"
          style={{ color: "var(--color-text-secondary)" }}
        >
          <ArrowLeft size={14} /> Вернуться на aineron.ru
        </a>
      </div>
    </main>
  );
}
