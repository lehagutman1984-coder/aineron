import Link from "next/link";
import type { ReactNode } from "react";
import { Info, AlertTriangle, Lightbulb, CheckCircle2 } from "lucide-react";

/**
 * DocKit — презентационные блоки документации (dark-aware, server-renderable).
 * Единый визуальный язык страниц /docs и /api-docs в стиле проекта.
 */

const CARD =
  "rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-6 shadow-sm " +
  "dark:border-[rgba(255,255,255,0.09)] dark:bg-[#211E1B] dark:shadow-none";

const TEXT = "text-[rgba(13,13,13,0.72)] dark:text-[rgba(236,236,236,0.68)]";
const HEAD = "text-[#1A1A1A] dark:text-[#EDE8E3]";

export function DocSection({
  title,
  intro,
  children,
}: {
  title?: string;
  intro?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className={CARD + " scroll-mt-24"}>
      {title && (
        <h2 className={`mb-3 text-[20px] font-semibold ${HEAD}`}>{title}</h2>
      )}
      {intro && (
        <p className={`mb-5 text-[16px] leading-relaxed ${TEXT}`}>{intro}</p>
      )}
      <div className="space-y-4">{children}</div>
    </section>
  );
}

export function Lead({ children }: { children: ReactNode }) {
  return (
    <p className={`text-[17px] leading-relaxed ${TEXT}`}>{children}</p>
  );
}

export function P({ children }: { children: ReactNode }) {
  return <p className={`text-[16px] leading-relaxed ${TEXT}`}>{children}</p>;
}

export function H3({ children }: { children: ReactNode }) {
  return (
    <h3 className={`mt-6 mb-1 text-[17px] font-semibold first:mt-0 ${HEAD}`}>
      {children}
    </h3>
  );
}

export function IC({ children }: { children: ReactNode }) {
  return (
    <code className="rounded-[5px] bg-[rgba(13,13,13,0.06)] px-1.5 py-0.5 font-mono text-[14px] text-[#1A1A1A] dark:bg-[rgba(255,255,255,0.09)] dark:text-[#EDE8E3]">
      {children}
    </code>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded-[5px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.04)] px-1.5 py-0.5 font-mono text-[13px] text-[#1A1A1A] dark:border-[rgba(255,255,255,0.14)] dark:bg-[rgba(255,255,255,0.06)] dark:text-[#EDE8E3]">
      {children}
    </kbd>
  );
}

export function A({ href, children }: { href: string; children: ReactNode }) {
  const external = href.startsWith("http") || href.startsWith("/api/");
  const cls = "text-[#D97757] hover:underline underline-offset-2";
  return external ? (
    <a href={href} target="_blank" rel="noopener noreferrer" className={cls}>
      {children}
    </a>
  ) : (
    <Link href={href} className={cls}>
      {children}
    </Link>
  );
}

export function UL({ children }: { children: ReactNode }) {
  return (
    <ul className={`space-y-2 text-[16px] leading-relaxed ${TEXT}`}>
      {children}
    </ul>
  );
}

export function LI({ children }: { children: ReactNode }) {
  return (
    <li className="flex gap-2.5">
      <span className="mt-[9px] h-[5px] w-[5px] shrink-0 rounded-full bg-[#D97757]" />
      <span>{children}</span>
    </li>
  );
}

export function Steps({ children }: { children: ReactNode }) {
  return <ol className="space-y-4">{children}</ol>;
}

export function Step({ n, children }: { n: number; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#1A1A1A] text-[13px] font-bold text-white dark:bg-[#D97757]">
        {n}
      </span>
      <div className={`pt-0.5 text-[16px] leading-relaxed ${TEXT}`}>{children}</div>
    </li>
  );
}

type CalloutType = "info" | "warn" | "tip" | "ok";

export function Callout({
  type = "info",
  title,
  children,
}: {
  type?: CalloutType;
  title?: string;
  children: ReactNode;
}) {
  const map = {
    info: {
      icon: <Info size={16} className="text-[#D97757]" />,
      cls: "border-[rgba(217,119,87,0.22)] bg-[rgba(217,119,87,0.06)]",
    },
    warn: {
      icon: <AlertTriangle size={16} className="text-[#ca8a04]" />,
      cls: "border-[rgba(202,138,4,0.25)] bg-[rgba(202,138,4,0.07)]",
    },
    tip: {
      icon: <Lightbulb size={16} className="text-[#7c5cff]" />,
      cls: "border-[rgba(124,92,255,0.25)] bg-[rgba(124,92,255,0.06)]",
    },
    ok: {
      icon: <CheckCircle2 size={16} className="text-[#16a34a]" />,
      cls: "border-[rgba(22,163,74,0.25)] bg-[rgba(22,163,74,0.06)]",
    },
  }[type];
  return (
    <div className={`flex gap-3 rounded-[12px] border p-4 ${map.cls}`}>
      <span className="mt-0.5 shrink-0">{map.icon}</span>
      <div className={`text-[15px] leading-relaxed ${TEXT}`}>
        {title && <p className={`mb-0.5 font-semibold ${HEAD}`}>{title}</p>}
        {children}
      </div>
    </div>
  );
}

export function FeatureGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-2">{children}</div>;
}

export function FeatureCard({
  icon,
  title,
  children,
}: {
  icon?: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.015)] p-4 dark:border-[rgba(255,255,255,0.08)] dark:bg-[rgba(255,255,255,0.02)]">
      <div className="mb-1.5 flex items-center gap-2">
        {icon && <span className="text-[#D97757]">{icon}</span>}
        <p className={`font-semibold ${HEAD}`}>{title}</p>
      </div>
      <p className={`text-[15px] leading-relaxed ${TEXT}`}>{children}</p>
    </div>
  );
}

export function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-4 dark:border-[rgba(255,255,255,0.09)] dark:bg-[#211E1B]">
      <p className="text-[12px] font-medium uppercase tracking-wider text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.40)]">
        {label}
      </p>
      <p className="mt-1 font-mono text-[15px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
        {value}
      </p>
    </div>
  );
}

export function DataTable({
  head,
  rows,
}: {
  head: string[];
  rows: ReactNode[][];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[15px]">
        <thead>
          <tr className="border-b border-[rgba(13,13,13,0.10)] dark:border-[rgba(255,255,255,0.10)]">
            {head.map((h, i) => (
              <th
                key={i}
                className="pb-2.5 pr-4 text-left font-medium text-[rgba(13,13,13,0.42)] dark:text-[rgba(236,236,236,0.45)]"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[rgba(13,13,13,0.06)] dark:divide-[rgba(255,255,255,0.06)]">
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) => (
                <td
                  key={j}
                  className="py-2.5 pr-4 align-top text-[rgba(13,13,13,0.68)] dark:text-[rgba(236,236,236,0.64)]"
                >
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const METHOD_CLS: Record<string, string> = {
  GET: "bg-[rgba(22,163,74,0.12)] text-[#16a34a]",
  POST: "bg-[rgba(217,119,87,0.12)] text-[#D97757]",
  PATCH: "bg-[rgba(124,92,255,0.12)] text-[#7c5cff]",
  DELETE: "bg-[rgba(220,38,38,0.12)] text-[#dc2626]",
};

export function Method({ children }: { children: string }) {
  const cls = METHOD_CLS[children] ?? METHOD_CLS.GET;
  return (
    <span
      className={`inline-flex items-center rounded-[5px] px-2 py-0.5 font-mono text-[12px] font-semibold ${cls}`}
    >
      {children}
    </span>
  );
}

export function Path({ children }: { children: ReactNode }) {
  return (
    <span className="font-mono text-[14px] text-[rgba(13,13,13,0.72)] dark:text-[rgba(236,236,236,0.68)]">
      {children}
    </span>
  );
}
