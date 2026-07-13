import { FileText } from "lucide-react";

import { getTranslations, getLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { serverGetLegalDoc } from "@/lib/api/server";
import { supportEmail } from "@/lib/site";

export const dynamic = "force-dynamic";

export async function generateMetadata() {
  const locale = await getLocale();
  const doc = await serverGetLegalDoc("terms", locale);
  const t = await getTranslations("legalChrome");
  return {
    title: doc?.title ?? t("termsFallbackTitle"),
  };
}

export default async function TermsPage() {
  const t = await getTranslations("legalChrome");
  const locale = await getLocale();
  const doc = await serverGetLegalDoc("terms", locale);

  const date = doc?.last_updated
    ? new Date(doc.last_updated).toLocaleDateString(locale, {
        day: "2-digit",
        month: "long",
        year: "numeric",
      })
    : null;

  return (
    <div className="min-h-screen bg-[#FAF9F7] px-4 py-12">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex items-center gap-3">
          <FileText size={20} className="text-[rgba(13,13,13,0.45)]" />
          <Link
            href="/"
            className="text-[15px] text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A] transition-colors"
          >
            {t("breadcrumbHome")}
          </Link>
          <span className="text-[15px] text-[rgba(13,13,13,0.25)]">/</span>
          <span className="text-[15px] text-[rgba(13,13,13,0.65)]">{t("termsFallbackTitle")}</span>
        </div>

        <div className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 shadow-sm">
          <h1 className="mb-2 text-[26px] font-bold text-[#1A1A1A]">
            {doc?.title ?? t("termsFallbackTitle")}
          </h1>
          {date && (
            <p className="mb-8 text-[15px] text-[rgba(13,13,13,0.45)]">
              {t("lastUpdated", { date })}
            </p>
          )}

          {doc ? (
            <div
              className="prose prose-sm max-w-none text-[rgba(13,13,13,0.75)] [&_h2]:text-[18px] [&_h2]:font-semibold [&_h2]:text-[#1A1A1A] [&_h2]:mt-6 [&_h2]:mb-3 [&_p]:mb-3 [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_li]:mb-1 [&_strong]:text-[#1A1A1A] [&_a]:text-[#D97757] [&_a:hover]:underline"
              dangerouslySetInnerHTML={{ __html: doc.content }}
            />
          ) : (
            <p className="text-[16px] text-[rgba(13,13,13,0.55)]">
              {t("docInProgress")}{" "}
              <a href={`mailto:${supportEmail()}`} className="text-[#D97757] hover:underline">
                {supportEmail()}
              </a>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
