"use client";

import { Suspense } from "react";
import { CheckCircle } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

function PaymentSuccessContent() {
  const params = useSearchParams();
  const invId = params.get("InvId");

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#FAF9F7] px-4">
      <div className="w-full max-w-md rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 shadow-sm text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(217,119,87,0.10)]">
          <CheckCircle size={24} className="text-[#D97757]" />
        </div>
        <h1 className="mb-2 text-[22px] font-bold text-[#1A1A1A]">Оплата прошла успешно</h1>
        <p className="mb-6 text-[14px] text-[rgba(13,13,13,0.55)]">
          Средства зачислены на ваш счёт. Можете продолжать пользоваться сервисом.
        </p>
        {invId && (
          <p className="mb-6 text-[12px] text-[rgba(13,13,13,0.35)]">
            Номер платежа: {invId}
          </p>
        )}
        <Link
          href="/account/billing/"
          className="mb-4 flex h-10 w-full items-center justify-center rounded-[8px] bg-[#D97757] text-[14px] font-medium text-white hover:bg-[#C4623E] transition-colors"
        >
          Перейти к балансу
        </Link>
        <div className="border-t border-[rgba(13,13,13,0.08)] pt-4">
          <Link
            href="/"
            className="text-[13px] text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A] transition-colors"
          >
            На главную
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function PaymentSuccessPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-[#FAF9F7]" />}>
      <PaymentSuccessContent />
    </Suspense>
  );
}
