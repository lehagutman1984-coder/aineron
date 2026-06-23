"use client";

import { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Copy, Check, ChevronDown, ChevronUp, FileCode } from "lucide-react";
import type { Components } from "react-markdown";
import type { ComponentPropsWithoutRef } from "react";

// ── Code block with language label + copy button ────────────────────────────

function PreBlock({ children, ...props }: ComponentPropsWithoutRef<"pre">) {
  const ref = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);

  let lang = "";
  const child = Array.isArray(children) ? children[0] : children;
  if (
    child &&
    typeof child === "object" &&
    "props" in (child as object) &&
    typeof (child as { props?: { className?: string } }).props?.className === "string"
  ) {
    lang = ((child as { props: { className: string } }).props.className ?? "")
      .replace("language-", "")
      .split(" ")[0];
  }

  const copy = () => {
    const text = ref.current?.textContent ?? "";
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-4 overflow-hidden rounded-[10px] border border-[rgba(255,255,255,0.06)] bg-[#0f0f0f]">
      <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.04)] px-4 py-2">
        <span className="font-mono text-[10px] font-semibold uppercase tracking-widest text-[rgba(255,255,255,0.38)]">
          {lang || "code"}
        </span>
        <button
          onClick={copy}
          className="flex items-center gap-1.5 rounded-[5px] border border-[rgba(255,255,255,0.10)] px-2 py-1 text-[11px] font-medium text-[rgba(255,255,255,0.45)] transition-colors hover:bg-[rgba(255,255,255,0.08)] hover:text-[rgba(255,255,255,0.82)]"
        >
          {copied ? <Check size={11} /> : <Copy size={11} />}
          {copied ? "Скопировано" : "Копировать"}
        </button>
      </div>
      <pre
        ref={ref}
        className="m-0 overflow-x-auto px-4 py-3.5 font-mono text-[13px] leading-relaxed text-[#e0e0e0]"
        {...props}
      >
        {children}
      </pre>
    </div>
  );
}

// ── react-markdown component map ────────────────────────────────────────────

const components: Components = {
  pre: PreBlock as Components["pre"],

  code: ({ children, className, ...props }) => {
    if (className) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code
        className="rounded-[4px] bg-[rgba(13,13,13,0.07)] px-[0.35em] py-[0.1em] font-mono text-[0.84em] text-[#0d0d0d]"
        {...props}
      >
        {children}
      </code>
    );
  },

  a: ({ href, children, ...props }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[#0a7cff] underline underline-offset-2 transition-opacity hover:opacity-75"
      {...props}
    >
      {children}
    </a>
  ),

  table: ({ children, ...props }) => (
    <div className="my-4 overflow-x-auto rounded-[8px] border border-[rgba(13,13,13,0.10)]">
      <table className="w-full border-collapse text-[14px]" {...props}>
        {children}
      </table>
    </div>
  ),
  th: ({ children, ...props }) => (
    <th
      className="border-b border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.04)] px-3 py-2 text-left font-semibold"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td
      className="border-b border-[rgba(13,13,13,0.06)] px-3 py-2 last:border-b-0"
      {...props}
    >
      {children}
    </td>
  ),
  tr: ({ children, ...props }) => (
    <tr className="last:border-b-0 [&:last-child_td]:border-b-0" {...props}>
      {children}
    </tr>
  ),

  blockquote: ({ children, ...props }) => (
    <blockquote
      className="my-3 border-l-[3px] border-[rgba(13,13,13,0.18)] pl-4 italic text-[rgba(13,13,13,0.58)]"
      {...props}
    >
      {children}
    </blockquote>
  ),

  h1: ({ children, ...props }) => (
    <h1 className="mb-2 mt-5 text-[1.2rem] font-semibold text-[#0d0d0d]" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 className="mb-2 mt-4 text-[1.05rem] font-semibold text-[#0d0d0d]" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="mb-1.5 mt-3.5 text-[0.95rem] font-semibold text-[#0d0d0d]" {...props}>
      {children}
    </h3>
  ),

  input: ({ type, checked, ...props }) => {
    if (type === "checkbox") {
      return (
        <input
          type="checkbox"
          checked={checked}
          readOnly
          className="mr-1.5 accent-[#0a7cff]"
          {...props}
        />
      );
    }
    return <input type={type} {...props} />;
  },
};

// ── FILE block collapsed component ──────────────────────────────────────────

const EXT_LANG: Record<string, string> = {
  py: "python", ts: "typescript", tsx: "typescript", js: "javascript",
  jsx: "javascript", html: "html", css: "css", json: "json", yml: "yaml",
  yaml: "yaml", sh: "bash", bash: "bash", rs: "rust", go: "go",
  java: "java", rb: "ruby", php: "php", sql: "sql", xml: "xml", md: "markdown",
};

function FileBlock({ filePath, code, truncated }: { filePath: string; code: string; truncated?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const lineCount = code.split("\n").length;
  const ext = filePath.split(".").pop()?.toLowerCase() ?? "";
  const lang = EXT_LANG[ext] ?? "";

  const copy = () => {
    navigator.clipboard.writeText(code).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 overflow-hidden rounded-[10px] border border-[rgba(0,122,255,0.25)] bg-[rgba(0,122,255,0.04)]">
      {truncated && (
        <div className="px-4 py-1.5 bg-[rgba(255,149,0,0.08)] border-b border-[rgba(255,149,0,0.20)]">
          <span className="text-[11px] text-[#ff9500]">Файл обрезан API (лимит ~55K симв.) — кнопка коммита недоступна. Запросите конкретную функцию.</span>
        </div>
      )}
      {/* Header — always visible */}
      <div
        className="flex cursor-pointer items-center gap-2.5 px-4 py-2.5 transition-colors hover:bg-[rgba(0,122,255,0.06)]"
        onClick={() => setExpanded((v) => !v)}
      >
        <FileCode size={14} className="shrink-0 text-[#0a7cff]" />
        <span className="flex-1 font-mono text-[13px] font-medium text-[#0a7cff]">
          {filePath}
        </span>
        <span className="text-[11px] text-[rgba(0,0,0,0.38)]">
          {lineCount} строк
        </span>
        {expanded ? (
          <ChevronUp size={14} className="text-[rgba(0,0,0,0.38)]" />
        ) : (
          <ChevronDown size={14} className="text-[rgba(0,0,0,0.38)]" />
        )}
      </div>

      {/* Expanded code */}
      {expanded && (
        <div className="border-t border-[rgba(0,122,255,0.15)] bg-[#0f0f0f]">
          <div className="flex items-center justify-between px-4 py-2">
            <span className="font-mono text-[10px] font-semibold uppercase tracking-widest text-[rgba(255,255,255,0.38)]">
              {lang || "code"}
            </span>
            <button
              onClick={copy}
              className="flex items-center gap-1.5 rounded-[5px] border border-[rgba(255,255,255,0.10)] px-2 py-1 text-[11px] font-medium text-[rgba(255,255,255,0.45)] transition-colors hover:bg-[rgba(255,255,255,0.08)] hover:text-[rgba(255,255,255,0.82)]"
            >
              {copied ? <Check size={11} /> : <Copy size={11} />}
              {copied ? "Скопировано" : "Копировать"}
            </button>
          </div>
          <pre className="m-0 overflow-x-auto px-4 pb-4 font-mono text-[13px] leading-relaxed text-[#e0e0e0]">
            <code className={lang ? `language-${lang}` : ""}>{code}</code>
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Content segmentation ─────────────────────────────────────────────────────

interface Segment {
  type: "text" | "file";
  content: string;
  filePath?: string;
  truncated?: boolean;
}

const FILE_BLOCK_RE = /===\s*FILE:\s*([^\n=]+?)\s*===\n([\s\S]*?)===\s*END FILE\s*===/g;

function parseSegments(raw: string): Segment[] {
  const text = raw
    .replace(/^===\s*RESPONSE\s*===\s*\n?/i, "")
    .replace(/\n?===\s*END RESPONSE\s*===\s*$/i, "");

  const segments: Segment[] = [];
  let lastIndex = 0;
  FILE_BLOCK_RE.lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = FILE_BLOCK_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "text", content: text.slice(lastIndex, match.index) });
    }
    segments.push({ type: "file", content: match[2], filePath: match[1].trim() });
    lastIndex = FILE_BLOCK_RE.lastIndex;
  }

  // Handle truncated (unclosed) FILE block at end of response
  const remaining = text.slice(lastIndex);
  const openBlockMatch = /===\s*FILE:\s*([^\n=]+?)\s*===\n([\s\S]*)$/.exec(remaining);
  if (openBlockMatch) {
    const beforeBlock = remaining.slice(0, openBlockMatch.index);
    if (beforeBlock.trim()) {
      segments.push({ type: "text", content: beforeBlock });
    }
    segments.push({ type: "file", content: openBlockMatch[2], filePath: openBlockMatch[1].trim(), truncated: true });
  } else if (remaining.length > 0) {
    segments.push({ type: "text", content: remaining });
  }

  return segments.length > 0 ? segments : [{ type: "text", content: text }];
}

// ── Public component ────────────────────────────────────────────────────────

export function MarkdownContent({ content }: { content: string }) {
  const segments = parseSegments(content);

  return (
    <div className="chat-md">
      {segments.map((seg, i) =>
        seg.type === "file" ? (
          <FileBlock key={i} filePath={seg.filePath!} code={seg.content.trimEnd()} truncated={seg.truncated} />
        ) : (
          <ReactMarkdown
            key={i}
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
            components={components}
          >
            {seg.content}
          </ReactMarkdown>
        )
      )}
    </div>
  );
}
