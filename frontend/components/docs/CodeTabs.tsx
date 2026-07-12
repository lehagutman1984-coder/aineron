"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { useTranslations } from "next-intl";

function CopyButton({ code }: { code: string }) {
  const t = useTranslations("chat");
  const [copied, setCopied] = useState(false);

  const handle = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button
      onClick={handle}
      className="flex items-center gap-1.5 rounded-[6px] px-2.5 py-1 text-[13px] font-medium text-[rgba(255,255,255,0.4)] hover:text-[rgba(255,255,255,0.75)] transition-colors"
    >
      {copied ? <Check size={11} /> : <Copy size={11} />}
      {copied ? t("copied") : t("copy")}
    </button>
  );
}

function CodeBlock({ code }: { code: string }) {
  return (
    <div className="bg-[#111]">
      <div className="flex items-center justify-end px-4 py-2 border-b border-[rgba(255,255,255,0.05)]">
        <CopyButton code={code} />
      </div>
      <pre className="overflow-x-auto px-5 py-4 text-[15px] leading-relaxed font-mono text-[rgba(255,255,255,0.82)]">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export interface CodeTabItem {
  key: string;
  label: string;
  code: string | string[];
}

export function CodeTabs({ tabs }: { tabs: CodeTabItem[] }) {
  const [active, setActive] = useState(tabs[0]?.key ?? "");
  const current = tabs.find((t) => t.key === active) ?? tabs[0];
  const blocks = current
    ? Array.isArray(current.code)
      ? current.code
      : [current.code]
    : [];

  return (
    <div className="overflow-hidden rounded-[12px] border border-[rgba(13,13,13,0.10)]">
      <div className="flex flex-wrap gap-0.5 bg-[rgba(13,13,13,0.03)] px-2 py-1.5 border-b border-[rgba(13,13,13,0.08)]">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActive(t.key)}
            className={`rounded-[7px] px-3 py-1 text-[14px] font-medium transition-all ${
              t.key === active
                ? "bg-white text-[#1A1A1A] shadow-sm"
                : "text-[rgba(13,13,13,0.5)] hover:text-[#1A1A1A]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="overflow-hidden rounded-b-[10px]">
        {blocks.map((code, i) => (
          <div key={i} className={i > 0 ? "border-t border-[rgba(255,255,255,0.05)]" : ""}>
            <CodeBlock code={code} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function StandaloneCodeBlock({ code }: { code: string }) {
  return (
    <div className="overflow-hidden rounded-[12px] border border-[rgba(13,13,13,0.10)]">
      <CodeBlock code={code} />
    </div>
  );
}
