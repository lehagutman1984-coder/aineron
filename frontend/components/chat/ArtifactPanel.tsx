"use client";

import { useState, useEffect, useRef } from "react";
import { X, Code2, Eye, Copy, Check, ExternalLink } from "lucide-react";

export type ArtifactType = "react" | "html" | "svg" | "mermaid" | "code";

export interface Artifact {
  type: ArtifactType;
  lang: string;
  code: string;
  title?: string;
}

/** Extract the first renderable artifact from an assistant message's plain text. */
export function extractArtifact(content: string): Artifact | null {
  if (!content) return null;

  // Strip HTML tags to get plain code text (messages are stored as HTML)
  const plain = content
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/?(p|div|li|ul|ol)[^>]*>/gi, "\n")
    .replace(/<[^>]+>/g, "");

  // Match fenced code blocks: ```lang\ncode\n```
  const fenced = /```(\w+)?\n([\s\S]*?)```/g;
  let match: RegExpExecArray | null;

  while ((match = fenced.exec(plain)) !== null) {
    const lang = (match[1] || "").toLowerCase();
    const code = match[2].trim();

    if (["jsx", "tsx", "react"].includes(lang)) {
      return { type: "react", lang, code, title: "React компонент" };
    }
    if (lang === "html") {
      return { type: "html", lang, code, title: "HTML preview" };
    }
    if (lang === "svg") {
      return { type: "svg", lang, code, title: "SVG" };
    }
    if (lang === "mermaid") {
      return { type: "mermaid", lang, code, title: "Диаграмма" };
    }
  }

  // Also check for raw <svg> tags in HTML content
  if (/<svg[\s\S]*?<\/svg>/i.test(content)) {
    const svgMatch = content.match(/<svg[\s\S]*?<\/svg>/i);
    if (svgMatch) {
      return { type: "svg", lang: "svg", code: svgMatch[0], title: "SVG" };
    }
  }

  return null;
}

function SandboxedPreview({ artifact }: { artifact: Artifact }) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    let html = "";

    if (artifact.type === "svg") {
      html = `<!DOCTYPE html><html><body style="margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#fff;">${artifact.code}</body></html>`;
    } else if (artifact.type === "html") {
      html = artifact.code.includes("<!DOCTYPE") ? artifact.code : `<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{font-family:system-ui,sans-serif;margin:16px}</style></head><body>${artifact.code}</body></html>`;
    } else if (artifact.type === "react") {
      // Wrap in basic React CDN setup so simple components render
      html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://unpkg.com/react@18/umd/react.development.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <style>body{font-family:system-ui,sans-serif;margin:16px}</style>
</head>
<body>
  <div id="root"></div>
  <script type="text/babel">
    ${artifact.code}
    // Try to render the last exported/defined component
    const root = ReactDOM.createRoot(document.getElementById('root'));
    try {
      const exportedKeys = Object.keys(window).filter(k => k[0] === k[0].toUpperCase() && typeof window[k] === 'function');
      const Comp = typeof App !== 'undefined' ? App : (exportedKeys.length ? window[exportedKeys[exportedKeys.length-1]] : () => React.createElement('div', null, 'No component found'));
      root.render(React.createElement(Comp));
    } catch(e) { root.render(React.createElement('pre', null, String(e))); }
  </script>
</body>
</html>`;
    } else if (artifact.type === "mermaid") {
      html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
</head>
<body style="margin:16px">
  <div class="mermaid">${artifact.code}</div>
  <script>mermaid.initialize({ startOnLoad: true, theme: 'default' });</script>
</body>
</html>`;
    }

    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    iframe.src = url;
    return () => URL.revokeObjectURL(url);
  }, [artifact]);

  return (
    <iframe
      ref={iframeRef}
      sandbox="allow-scripts allow-same-origin"
      className="h-full w-full border-0"
      title="Artifact preview"
    />
  );
}

interface ArtifactPanelProps {
  artifact: Artifact;
  onClose: () => void;
}

export function ArtifactPanel({ artifact, onClose }: ArtifactPanelProps) {
  const [tab, setTab] = useState<"preview" | "code">(
    artifact.type === "mermaid" ? "preview" : "preview"
  );
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(artifact.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex h-full flex-col" style={{ borderLeft: "1px solid var(--border-secondary)" }}>
      {/* Header */}
      <div className="flex shrink-0 items-center gap-2 border-b border-[rgba(13,13,13,0.08)] px-3 py-2.5 dark:border-[rgba(255,255,255,0.08)]">
        <Code2 size={14} className="shrink-0 text-[#D97757]" />
        <span className="flex-1 truncate text-[15px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
          {artifact.title || "Артефакт"}
        </span>
        <div className="flex items-center gap-1">
          {/* Tab switcher */}
          <div className="flex rounded-[6px] bg-[rgba(13,13,13,0.06)] p-0.5 dark:bg-[rgba(255,255,255,0.06)]">
            <button
              onClick={() => setTab("preview")}
              className={`flex items-center gap-1 rounded-[4px] px-2 py-0.5 text-[13px] font-medium transition-all ${tab === "preview" ? "bg-white text-[#1A1A1A] shadow-sm dark:bg-[rgba(255,255,255,0.12)] dark:text-[#EDE8E3]" : "text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.4)]"}`}
            >
              <Eye size={11} />
              Preview
            </button>
            <button
              onClick={() => setTab("code")}
              className={`flex items-center gap-1 rounded-[4px] px-2 py-0.5 text-[13px] font-medium transition-all ${tab === "code" ? "bg-white text-[#1A1A1A] shadow-sm dark:bg-[rgba(255,255,255,0.12)] dark:text-[#EDE8E3]" : "text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.4)]"}`}
            >
              <Code2 size={11} />
              Код
            </button>
          </div>
          <button
            onClick={handleCopy}
            className="flex h-6 w-6 items-center justify-center rounded-[5px] text-[rgba(13,13,13,0.4)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.4)] dark:hover:bg-[rgba(255,255,255,0.08)]"
            title="Скопировать код"
          >
            {copied ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
          </button>
          <button
            onClick={onClose}
            className="flex h-6 w-6 items-center justify-center rounded-[5px] text-[rgba(13,13,13,0.4)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.4)] dark:hover:bg-[rgba(255,255,255,0.08)]"
          >
            <X size={12} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="min-h-0 flex-1 overflow-hidden">
        {tab === "preview" ? (
          <SandboxedPreview artifact={artifact} />
        ) : (
          <pre className="h-full overflow-auto p-4 font-mono text-[14px] leading-relaxed text-[#1A1A1A] dark:text-[#EDE8E3]">
            <code>{artifact.code}</code>
          </pre>
        )}
      </div>
    </div>
  );
}
