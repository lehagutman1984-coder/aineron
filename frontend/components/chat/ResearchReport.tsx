"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { ChevronDown, ChevronRight, BookOpen, Download } from "lucide-react";

interface Props {
  html: string;
  plainText?: string;
}

function CollapsibleSection({ title, html }: { title: string; html: string }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="border-b border-[rgba(13,13,13,0.06)] last:border-0 dark:border-[rgba(255,255,255,0.05)]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 py-2 text-left text-[15px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]"
      >
        {open ? (
          <ChevronDown size={13} className="shrink-0 text-[rgba(13,13,13,0.4)]" />
        ) : (
          <ChevronRight size={13} className="shrink-0 text-[rgba(13,13,13,0.4)]" />
        )}
        {title}
      </button>
      {open && (
        <div
          className="pb-3 pl-5 text-[15px] leading-relaxed text-[rgba(13,13,13,0.8)] dark:text-[rgba(236,236,236,0.75)]"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      )}
    </div>
  );
}

function parseReportSections(html: string): Array<{ title: string; html: string }> {
  const h2Re = /<h2[^>]*>(.*?)<\/h2>/gi;
  const sections: Array<{ title: string; start: number }> = [];
  let m: RegExpExecArray | null;
  while ((m = h2Re.exec(html)) !== null) {
    sections.push({ title: m[1].replace(/<[^>]+>/g, ""), start: m.index });
  }
  if (sections.length === 0) return [{ title: "", html }];
  return sections.map((sec, i) => {
    const nextStart = sections[i + 1]?.start ?? html.length;
    const sectionHtml = html.slice(sec.start, nextStart).replace(/^<h2[^>]*>.*?<\/h2>/i, "");
    return { title: sec.title, html: sectionHtml };
  });
}

export function ResearchReport({ html, plainText }: Props) {
  const t = useTranslations("chat.researchReport");
  const sections = parseReportSections(html);

  const handleExport = useCallback(() => {
    const content = plainText || html.replace(/<[^>]+>/g, "");
    const blob = new Blob([content], { type: "text/markdown; charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `research-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [html, plainText]);

  if (sections.length <= 1) {
    return (
      <div className="mt-3 rounded-[12px] border border-[rgba(217,119,87,0.15)] bg-[rgba(217,119,87,0.02)]">
        <div className="flex items-center gap-2 border-b border-[rgba(217,119,87,0.1)] px-4 py-2.5">
          <BookOpen size={13} className="text-[#D97757]" />
          <span className="flex-1 text-[13px] font-semibold uppercase tracking-wide text-[#D97757]">
            {t("title")}
          </span>
          <button
            onClick={handleExport}
            title={t("downloadTitle")}
            className="flex items-center gap-1 rounded-[5px] px-2 py-1 text-[13px] text-[rgba(13,13,13,0.45)] transition hover:bg-[rgba(217,119,87,0.08)] hover:text-[#D97757] dark:text-[rgba(236,236,236,0.4)]"
          >
            <Download size={11} />
            MD
          </button>
        </div>
        <div
          className="px-4 py-3 text-[16px] leading-relaxed"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-[12px] border border-[rgba(217,119,87,0.15)] bg-[rgba(217,119,87,0.02)]">
      <div className="flex items-center gap-2 border-b border-[rgba(217,119,87,0.1)] px-4 py-2.5">
        <BookOpen size={13} className="text-[#D97757]" />
        <span className="flex-1 text-[13px] font-semibold uppercase tracking-wide text-[#D97757]">
          {t("title")}
        </span>
        <button
          onClick={handleExport}
          title={t("downloadTitle")}
          className="flex items-center gap-1 rounded-[5px] px-2 py-1 text-[13px] text-[rgba(13,13,13,0.45)] transition hover:bg-[rgba(217,119,87,0.08)] hover:text-[#D97757] dark:text-[rgba(236,236,236,0.4)]"
        >
          <Download size={11} />
          MD
        </button>
      </div>
      <div className="px-4 py-1">
        {sections.map((s, i) => (
          <CollapsibleSection key={i} title={s.title} html={s.html} />
        ))}
      </div>
    </div>
  );
}
