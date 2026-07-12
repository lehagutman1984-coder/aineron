import type { ReactNode } from "react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

export default async function AuthLayout({ children }: { children: ReactNode }) {
  const t = await getTranslations("auth");
  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        {children}
        <p className="mt-8 text-center text-[14px] text-[rgba(13,13,13,0.4)]">
          {t("agreePrefix")}{" "}
          <Link href="/legal/terms/" className="hover:text-[#D97757] underline-offset-2 hover:underline">
            {t("agreeTerms")}
          </Link>{" "}
          {t("agreeAnd")}{" "}
          <Link href="/legal/privacy/" className="hover:text-[#D97757] underline-offset-2 hover:underline">
            {t("agreePrivacy")}
          </Link>
        </p>
      </div>
    </div>
  );
}
