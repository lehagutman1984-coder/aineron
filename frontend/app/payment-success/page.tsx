"use client";

import { Suspense } from "react";
import { CheckCircle } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

function PaymentSuccessContent() {
  const params = useSearchParams();
  const invId = params.get("InvId");

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f5f5f7] px-4">
      <div className="w-full max-w-md rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 shadow-sm text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(29,214,193,0.10)]">
          <CheckCircle size={24} className="text-[#1dd6c1]" />
        </div>
        <h1 className="mb-2 text-[22px] font-bold text-[#0d0d0d]">Оплата прошла успешно</h1>
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
          className="mb-4 flex h-10 w-full items-center justify-center rounded-[8px] bg-[#f0a38a] text-[14px] font-medium text-white hover:bg-[#0066cc] transition-colors"
        >
          Перейти к балансу
        </Link>
        <div className="border-t border-[rgba(13,13,13,0.08)] pt-4">
          <Link
            href="/"
            className="text-[13px] text-[rgba(13,13,13,0.45)] hover:text-[#0d0d0d] transition-colors"
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
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-[#f5f5f7]" />}>
      <PaymentSuccessContent />
    </Suspense>
  );
}
