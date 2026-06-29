"use client";

import { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Copy, Check, ChevronDown, ChevronUp, FileCode, Pencil, Download, Maximize2, X } from "lucide-react";
import type { Components } from "react-markdown";
import type { ComponentPropsWithoutRef } from "react";

// ── Fullscreen modal overlay ─────────────────────────────────────────────────

function FullscreenModal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="flex h-[95vh] w-[95vw] flex-col overflow-hidden rounded-[12px] border border-[rgba(255,255,255,0.10)] bg-[#0f0f0f] shadow-2xl">
        <div className="flex shrink-0 items-center justify-between border-b border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.04)] px-4 py-2.5">
          <span className="font-mono text-[12px] font-semibold text-[rgba(255,255,255,0.55)]">{title}</span>
          <button
            onClick={onClose}
            className="flex items-center gap-1.5 rounded-[5px] border border-[rgba(255,255,255,0.10)] px-2.5 py-1 text-[11px] text-[rgba(255,255,255,0.45)] transition-colors hover:bg-[rgba(255,255,255,0.08)] hover:text-white"
          >
            <X size={12} /> Закрыть
          </button>
        </div>
        <div className="flex-1 overflow-auto">
          {children}
        </div>
      </div>
    </div>
  );
}

// ── Code block with language label + copy button ────────────────────────────

function PreBlock({ children, ...props }: ComponentPropsWithoutRef<"pre">) {
  const ref = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

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

  const EXT_MAP: Record<string, string> = {
    python: "py", typescript: "ts", javascript: "js", tsx: "tsx",
    jsx: "jsx", html: "html", css: "css", json: "json", yaml: "yml",
    bash: "sh", sh: "sh", rust: "rs", go: "go", java: "java",
    ruby: "rb", php: "php", sql: "sql", xml: "xml", markdown: "md",
  };

  const copy = () => {
    const text = ref.current?.textContent ?? "";
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const download = () => {
    const code = ref.current?.textContent ?? "";
    const ext = EXT_MAP[lang] ?? (lang || "txt");
    const blob = new Blob([code], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `code.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const toolbar = (
    <div className="flex items-center gap-1.5">
      <button
        onClick={download}
        className="flex items-center gap-1.5 rounded-[5px] border border-[rgba(255,255,255,0.10)] px-2 py-1 text-[11px] font-medium text-[rgba(255,255,255,0.45)] transition-colors hover:bg-[rgba(255,255,255,0.08)] hover:text-[rgba(255,255,255,0.82)]"
      >
        <Download size={11} /> Скачать
      </button>
      <button
        onClick={copy}
        className="flex items-center gap-1.5 rounded-[5px] border border-[rgba(255,255,255,0.10)] px-2 py-1 text-[11px] font-medium text-[rgba(255,255,255,0.45)] transition-colors hover:bg-[rgba(255,255,255,0.08)] hover:text-[rgba(255,255,255,0.82)]"
      >
        {copied ? <Check size={11} /> : <Copy size={11} />}
        {copied ? "Скопировано" : "Копировать"}
      </button>
      <button
        onClick={() => setFullscreen(true)}
        className="flex items-center gap-1.5 rounded-[5px] border border-[rgba(255,255,255,0.10)] px-2 py-1 text-[11px] font-medium text-[rgba(255,255,255,0.45)] transition-colors hover:bg-[rgba(255,255,255,0.08)] hover:text-[rgba(255,255,255,0.82)]"
      >
        <Maximize2 size={11} /> Развернуть
      </button>
    </div>
  );

  return (
    <>
      {fullscreen && (
        <FullscreenModal title={lang || "code"} onClose={() => setFullscreen(false)}>
          <pre
            className="m-0 h-full overflow-auto px-6 py-5 font-mono text-[13px] leading-relaxed text-[#e0e0e0]"
          >
            {children}
          </pre>
        </FullscreenModal>
      )}
      <div className="my-4 overflow-hidden rounded-[10px] border border-[#413c69] bg-[#1e2034]">
        <div className="flex items-center justify-between border-b border-[rgba(255, 255, 255, 0.06)] bg-[rgba(37, 41, 68, 0.04)] px-4 py-2">
          <span className="font-mono text-[10px] font-semibold uppercase tracking-widest text-[rgba(255,255,255,0.38)]">
            {lang || "code"}
          </span>
          {toolbar}
        </div>
        <pre
          ref={ref}
          className="m-0 overflow-x-auto px-4 py-3.5 font-mono text-[13px] leading-relaxed text-[#e0e0e0]"
          {...props}
        >
          {children}
        </pre>
      </div>
    </>
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
        className="rounded-[4px] bg-[rgba(13,13,13,0.07)] px-[0.35em] py-[0.1em] font-mono text-[0.84em] text-[#1A1A1A]"
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
      className="text-[#D97757] underline underline-offset-2 transition-opacity hover:opacity-75"
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
    <h1 className="mb-2 mt-5 text-[1.2rem] font-semibold text-[#1A1A1A]" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 className="mb-2 mt-4 text-[1.05rem] font-semibold text-[#1A1A1A]" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="mb-1.5 mt-3.5 text-[0.95rem] font-semibold text-[#1A1A1A]" {...props}>
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
          className="mr-1.5 accent-[#D97757]"
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

  const download = () => {
    const blob = new Blob([code], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filePath.split("/").pop() ?? filePath;
    a.click();
    URL.revokeObjectURL(url);
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
        <FileCode size={14} className="shrink-0 text-[#D97757]" />
        <span className="flex-1 font-mono text-[13px] font-medium text-[#D97757]">
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
            <div className="flex items-center gap-1.5">
              <button
                onClick={download}
                className="flex items-center gap-1.5 rounded-[5px] border border-[rgba(255,255,255,0.10)] px-2 py-1 text-[11px] font-medium text-[rgba(255,255,255,0.45)] transition-colors hover:bg-[rgba(255,255,255,0.08)] hover:text-[rgba(255,255,255,0.82)]"
              >
                <Download size={11} />
                Скачать
              </button>
              <button
                onClick={copy}
                className="flex items-center gap-1.5 rounded-[5px] border border-[rgba(255,255,255,0.10)] px-2 py-1 text-[11px] font-medium text-[rgba(255,255,255,0.45)] transition-colors hover:bg-[rgba(255,255,255,0.08)] hover:text-[rgba(255,255,255,0.82)]"
              >
                {copied ? <Check size={11} /> : <Copy size={11} />}
                {copied ? "Скопировано" : "Копировать"}
              </button>
            </div>
          </div>
          <pre className="m-0 overflow-x-auto px-4 pb-4 font-mono text-[13px] leading-relaxed text-[#e0e0e0]">
            <code className={lang ? `language-${lang}` : ""}>{code}</code>
          </pre>
        </div>
      )}
    </div>
  );
}

// ── EDIT block component ─────────────────────────────────────────────────────

interface EditHunk {
  search: string;
  replace: string;
}

function DiffHunk({ hunk, dark }: { hunk: EditHunk; dark: boolean }) {
  const [copiedSearch, setCopiedSearch] = useState(false);
  const [copiedReplace, setCopiedReplace] = useState(false);

  const copySearch = () => {
    navigator.clipboard.writeText(hunk.search.trimEnd()).catch(() => {});
    setCopiedSearch(true);
    setTimeout(() => setCopiedSearch(false), 2000);
  };
  const copyReplace = () => {
    navigator.clipboard.writeText(hunk.replace.trimEnd()).catch(() => {});
    setCopiedReplace(true);
    setTimeout(() => setCopiedReplace(false), 2000);
  };

  const btnCls = dark
    ? "flex items-center gap-1 rounded-[4px] border border-[rgba(255,255,255,0.12)] px-1.5 py-0.5 text-[10px] text-[rgba(255,255,255,0.40)] transition-colors hover:bg-[rgba(255,255,255,0.08)] hover:text-[rgba(255,255,255,0.80)]"
    : "flex items-center gap-1 rounded-[4px] border border-[rgba(0,0,0,0.10)] px-1.5 py-0.5 text-[10px] text-[rgba(0,0,0,0.35)] transition-colors hover:bg-[rgba(0,0,0,0.06)] hover:text-[rgba(0,0,0,0.65)]";

  return (
    <div className={`border-b last:border-b-0 ${dark ? "border-[rgba(255,255,255,0.06)]" : "border-[rgba(0,200,100,0.10)]"}`}>
      <div className="grid grid-cols-2">
        <div className={`border-r ${dark ? "border-[rgba(255,255,255,0.08)] bg-[rgba(255,60,60,0.12)]" : "border-[rgba(0,200,100,0.15)] bg-[rgba(255,60,60,0.05)]"}`}>
          <div className={`flex items-center justify-between border-b px-3 py-1 ${dark ? "border-[rgba(255,60,60,0.20)]" : "border-[rgba(255,60,60,0.12)]"}`}>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[rgba(220,80,80,0.9)]">Было</span>
            <button onClick={copySearch} className={btnCls}>
              {copiedSearch ? <Check size={10} /> : <Copy size={10} />}
              {copiedSearch ? "Скопировано" : "Копировать"}
            </button>
          </div>
          <pre className={`m-0 overflow-x-auto px-3 py-2.5 font-mono text-[12px] leading-relaxed ${dark ? "text-[rgba(255,255,255,0.82)]" : "text-[rgba(0,0,0,0.75)]"}`}>
            {hunk.search.trimEnd()}
          </pre>
        </div>
        <div className={dark ? "bg-[rgba(0,200,100,0.12)]" : "bg-[rgba(0,200,100,0.05)]"}>
          <div className={`flex items-center justify-between border-b px-3 py-1 ${dark ? "border-[rgba(0,200,100,0.20)]" : "border-[rgba(0,200,100,0.12)]"}`}>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[rgba(0,200,100,0.9)]">Стало</span>
            <button onClick={copyReplace} className={btnCls}>
              {copiedReplace ? <Check size={10} /> : <Copy size={10} />}
              {copiedReplace ? "Скопировано" : "Копировать"}
            </button>
          </div>
          <pre className={`m-0 overflow-x-auto px-3 py-2.5 font-mono text-[12px] leading-relaxed ${dark ? "text-[rgba(255,255,255,0.82)]" : "text-[rgba(0,0,0,0.75)]"}`}>
            {hunk.replace.trimEnd() || "(удалено)"}
          </pre>
        </div>
      </div>
    </div>
  );
}

function EditBlock({ filePath, hunks }: { filePath: string; hunks: EditHunk[] }) {
  const [expanded, setExpanded] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  const renderDiff = (dark: boolean) => (
    <div>
      {hunks.map((hunk, idx) => (
        <DiffHunk key={idx} hunk={hunk} dark={dark} />
      ))}
    </div>
  );

  return (
    <>
      {fullscreen && (
        <FullscreenModal title={filePath} onClose={() => setFullscreen(false)}>
          {renderDiff(true)}
        </FullscreenModal>
      )}
    <div className="my-3 overflow-hidden rounded-[10px] border border-[rgba(0,200,100,0.25)] bg-[rgba(0,200,100,0.04)]">
      {/* Header */}
      <div
        className="flex cursor-pointer items-center gap-2.5 px-4 py-2.5 transition-colors hover:bg-[rgba(0,200,100,0.07)]"
        onClick={() => setExpanded((v) => !v)}
      >
        <Pencil size={14} className="shrink-0 text-[#00c864]" />
        <span className="flex-1 font-mono text-[13px] font-medium text-[#00c864]">
          {filePath}
        </span>
        <span className="text-[11px] text-[rgba(0,0,0,0.38)]">
          {hunks.length} {hunks.length === 1 ? "правка" : "правок"}
        </span>
        <button
          onClick={(e) => { e.stopPropagation(); setFullscreen(true); }}
          className="rounded-[4px] p-1 text-[rgba(0,0,0,0.30)] transition-colors hover:bg-[rgba(0,200,100,0.12)] hover:text-[#00c864]"
          title="Развернуть"
        >
          <Maximize2 size={13} />
        </button>
        {expanded ? (
          <ChevronUp size={14} className="text-[rgba(0,0,0,0.38)]" />
        ) : (
          <ChevronDown size={14} className="text-[rgba(0,0,0,0.38)]" />
        )}
      </div>

      {/* Expanded diff hunks */}
      {expanded && (
        <div className="border-t border-[rgba(0,200,100,0.15)]">
          {renderDiff(false)}
        </div>
      )}
    </div>
    </>
  );
}

// ── Content segmentation ─────────────────────────────────────────────────────

interface Segment {
  type: "text" | "file" | "edit";
  content: string;
  filePath?: string;
  truncated?: boolean;
  hunks?: EditHunk[];
}

// NOTE: Паттерны должны быть идентичны commit_extract.py (_EDIT_BLOCK_RE, _HUNK_RE)
const FILE_BLOCK_RE = /===\s*FILE:\s*([^\n=]+?)\s*===\n([\s\S]*?)===\s*END FILE\s*===/g;
const EDIT_BLOCK_RE = /===\s*EDIT:\s*([^\n=]+?)\s*===\n([\s\S]*?)===\s*END EDIT\s*===/g;
// Tolerant: trailing whitespace after marker (matches Python _HUNK_RE)
const HUNK_RE = /<<<SEARCH>>>[ \t]*\n([\s\S]*?)<<<REPLACE>>>[ \t]*\n([\s\S]*?)<<<END>>>/g;

function parseHunks(body: string): EditHunk[] {
  const hunks: EditHunk[] = [];
  HUNK_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = HUNK_RE.exec(body)) !== null) {
    hunks.push({ search: m[1], replace: m[2] });
  }
  return hunks;
}

interface FoundBlock {
  start: number;
  end: number;
  type: "file" | "edit";
  filePath: string;
  /** raw inner body (for EDIT: hunk content; for FILE: file content) */
  body: string;
}

function collectBlocks(text: string): FoundBlock[] {
  const blocks: FoundBlock[] = [];

  FILE_BLOCK_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = FILE_BLOCK_RE.exec(text)) !== null) {
    blocks.push({ start: m.index, end: FILE_BLOCK_RE.lastIndex, type: "file", filePath: m[1].trim(), body: m[2] });
  }

  EDIT_BLOCK_RE.lastIndex = 0;
  while ((m = EDIT_BLOCK_RE.exec(text)) !== null) {
    blocks.push({ start: m.index, end: EDIT_BLOCK_RE.lastIndex, type: "edit", filePath: m[1].trim().replace(/^\//, ""), body: m[2] });
  }

  return blocks.sort((a, b) => a.start - b.start);
}

function parseSegments(raw: string): Segment[] {
  const text = raw
    .replace(/^===\s*RESPONSE\s*===\s*\n?/i, "")
    .replace(/\n?===\s*END RESPONSE\s*===\s*$/i, "");

  const blocks = collectBlocks(text);
  const segments: Segment[] = [];
  let lastIndex = 0;

  for (const block of blocks) {
    if (block.start > lastIndex) {
      segments.push({ type: "text", content: text.slice(lastIndex, block.start) });
    }
    if (block.type === "file") {
      segments.push({ type: "file", content: block.body, filePath: block.filePath });
    } else {
      const hunks = parseHunks(block.body);
      if (hunks.length > 0) {
        segments.push({ type: "edit", content: "", filePath: block.filePath, hunks });
      }
    }
    lastIndex = block.end;
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
        ) : seg.type === "edit" ? (
          <EditBlock key={i} filePath={seg.filePath!} hunks={seg.hunks!} />
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
