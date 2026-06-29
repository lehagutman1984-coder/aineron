"use client";

import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { GitCommit, Edit2, Eye, Loader2, X, Maximize2, Minimize2, Plus, Minus } from "lucide-react";
import { javascript } from "@codemirror/lang-javascript";
import { html } from "@codemirror/lang-html";
import { css } from "@codemirror/lang-css";
import type { Extension } from "@codemirror/state";

const CodeMirrorEditor = dynamic(
  async () => {
    const { default: CodeMirror } = await import("@uiw/react-codemirror");
    return CodeMirror;
  },
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center py-10 text-[14px] text-[rgba(13,13,13,0.38)]">
        <Loader2 size={14} className="animate-spin mr-1.5" />
        Загрузка редактора...
      </div>
    ),
  }
);

function detectLanguage(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    ts: "typescript", tsx: "typescript", js: "javascript", jsx: "javascript",
    py: "python", md: "markdown", json: "json", html: "html", css: "css",
    sh: "shell", yml: "yaml", yaml: "yaml", rs: "rust", go: "go",
    java: "java", rb: "ruby", php: "php", sql: "sql", xml: "xml",
  };
  return map[ext] ?? "text";
}

function getLanguageExtensions(lang: string): Extension[] {
  switch (lang) {
    case "typescript": return [javascript({ typescript: true, jsx: true })];
    case "javascript": return [javascript({ jsx: true })];
    case "html":       return [html()];
    case "css":        return [css()];
    default:           return [];
  }
}

interface Props {
  filePath: string;
  initialContent: string;
  readOnly?: boolean;
  onCommit?: (content: string, message: string) => Promise<void>;
  onClose?: () => void;
}

const FONT_SIZES = [12, 14, 15, 16, 18];

export default function CodeEditor({
  filePath,
  initialContent,
  readOnly = false,
  onCommit,
  onClose,
}: Props) {
  const [content, setContent] = useState(initialContent);
  const [editMode, setEditMode] = useState(false);
  const [commitMsg, setCommitMsg] = useState("");
  const [committing, setCommitting] = useState(false);
  const [commitErr, setCommitErr] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [fontSizeIdx, setFontSizeIdx] = useState(2); // default: 15px

  const dirty = editMode && content !== initialContent;
  const lang = detectLanguage(filePath);
  const fontSize = FONT_SIZES[fontSizeIdx];

  // Esc closes fullscreen
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape" && expanded) setExpanded(false);
  }, [expanded]);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // beforeunload guard for unsaved changes
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const handleCommit = async () => {
    if (!onCommit || !commitMsg.trim() || !dirty) return;
    setCommitting(true);
    setCommitErr(null);
    try {
      await onCommit(content, commitMsg.trim());
      setEditMode(false);
      setCommitMsg("");
    } catch (e) {
      setCommitErr((e as Error).message ?? "Ошибка при коммите");
    } finally {
      setCommitting(false);
    }
  };

  const handleToggleEdit = () => {
    if (editMode && dirty) {
      if (!window.confirm("Есть несохранённые изменения. Отменить правки?")) return;
      setContent(initialContent);
    }
    setEditMode(!editMode);
    setCommitMsg("");
    setCommitErr(null);
  };

  const toolbar = (
    <div className="flex items-center gap-2 border-b border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] px-3 py-2 shrink-0">
      <span className="flex-1 truncate text-[14px] font-medium text-[rgba(13,13,13,0.60)]">{filePath}</span>

      {/* Font size controls */}
      <div className="flex items-center gap-0.5">
        <button
          onClick={() => setFontSizeIdx((i) => Math.max(0, i - 1))}
          disabled={fontSizeIdx === 0}
          className="flex h-6 w-6 items-center justify-center rounded text-[rgba(13,13,13,0.40)] hover:bg-[rgba(13,13,13,0.07)] hover:text-[#1A1A1A] disabled:opacity-30 transition-colors"
          title="Уменьшить шрифт"
        >
          <Minus size={11} />
        </button>
        <span className="w-7 text-center text-[12px] text-[rgba(13,13,13,0.40)]">{fontSize}</span>
        <button
          onClick={() => setFontSizeIdx((i) => Math.min(FONT_SIZES.length - 1, i + 1))}
          disabled={fontSizeIdx === FONT_SIZES.length - 1}
          className="flex h-6 w-6 items-center justify-center rounded text-[rgba(13,13,13,0.40)] hover:bg-[rgba(13,13,13,0.07)] hover:text-[#1A1A1A] disabled:opacity-30 transition-colors"
          title="Увеличить шрифт"
        >
          <Plus size={11} />
        </button>
      </div>

      <div className="h-4 w-px bg-[rgba(13,13,13,0.10)]" />

      {!readOnly && (
        <button
          onClick={handleToggleEdit}
          className={`flex items-center gap-1 rounded px-2 py-0.5 text-[14px] transition-colors ${
            editMode
              ? "bg-[rgba(13,13,13,0.08)] text-[#1A1A1A]"
              : "text-[rgba(13,13,13,0.50)] hover:text-[#D97757]"
          }`}
        >
          {editMode ? <Eye size={12} /> : <Edit2 size={12} />}
          {editMode ? "Просмотр" : "Редактировать"}
        </button>
      )}

      {/* Expand/collapse */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex h-6 w-6 items-center justify-center rounded text-[rgba(13,13,13,0.40)] hover:bg-[rgba(13,13,13,0.07)] hover:text-[#1A1A1A] transition-colors"
        title={expanded ? "Свернуть (Esc)" : "Развернуть на весь экран"}
      >
        {expanded ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
      </button>

      {onClose && !expanded && (
        <button
          onClick={onClose}
          className="flex h-6 w-6 items-center justify-center rounded text-[rgba(13,13,13,0.38)] hover:text-[#1A1A1A] transition-colors"
        >
          <X size={13} />
        </button>
      )}
    </div>
  );

  const editorArea = (
    <div className="flex-1 overflow-auto min-h-0">
      <CodeMirrorEditor
        value={content}
        onChange={editMode ? setContent : undefined}
        readOnly={!editMode}
        height="100%"
        theme="light"
        extensions={getLanguageExtensions(lang)}
        basicSetup={{
          lineNumbers: true,
          foldGutter: true,
          highlightActiveLine: editMode,
          autocompletion: false,
        }}
        style={{ fontSize, height: "100%", lineHeight: 1.65 }}
      />
    </div>
  );

  const commitPanel = editMode && dirty && onCommit && (
    <div className="shrink-0 border-t border-[rgba(13,13,13,0.10)] bg-white px-3 py-2.5">
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={commitMsg}
          onChange={(e) => setCommitMsg(e.target.value)}
          placeholder="Сообщение коммита..."
          className="flex-1 rounded-[6px] border border-[rgba(13,13,13,0.16)] px-2.5 py-1.5 text-[15px] outline-none focus:border-[#D97757]"
          onKeyDown={(e) => { if (e.key === "Enter") handleCommit(); }}
        />
        <button
          onClick={handleCommit}
          disabled={!commitMsg.trim() || committing}
          className="flex items-center gap-1.5 rounded-[6px] bg-[#D97757] px-3 py-1.5 text-[14px] font-medium text-white disabled:opacity-50 hover:bg-[#C4623E] transition-colors"
        >
          {committing ? <Loader2 size={12} className="animate-spin" /> : <GitCommit size={12} />}
          Commit
        </button>
      </div>
      {commitErr && (
        <p className="mt-1.5 text-[13px] text-red-500">{commitErr}</p>
      )}
    </div>
  );

  if (expanded) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col bg-white">
        {toolbar}
        {editorArea}
        {commitPanel}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {toolbar}
      {editorArea}
      {commitPanel}
    </div>
  );
}
