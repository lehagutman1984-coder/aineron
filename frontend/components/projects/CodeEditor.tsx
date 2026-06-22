"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { GitCommit, Edit2, Eye, Loader2, X } from "lucide-react";

// CodeMirror lazy-loaded (client only — avoid SSR issues)
const CodeMirrorEditor = dynamic(
  async () => {
    const { default: CodeMirror } = await import("@uiw/react-codemirror");
    return CodeMirror;
  },
  { ssr: false, loading: () => <div className="flex items-center justify-center py-10 text-[12px] text-[rgba(13,13,13,0.38)]"><Loader2 size={14} className="animate-spin mr-1.5" />Загрузка редактора...</div> }
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

interface Props {
  filePath: string;
  initialContent: string;
  readOnly?: boolean;
  onCommit?: (content: string, message: string) => Promise<void>;
  onClose?: () => void;
}

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
  const dirty = editMode && content !== initialContent;
  const lang = detectLanguage(filePath);

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

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 border-b border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] px-3 py-1.5 shrink-0">
        <span className="flex-1 truncate text-[11px] text-[rgba(13,13,13,0.55)]">{filePath}</span>
        {!readOnly && (
          <button
            onClick={handleToggleEdit}
            className={`flex items-center gap-1 rounded px-2 py-0.5 text-[11px] transition-colors ${
              editMode
                ? "bg-[rgba(13,13,13,0.08)] text-[#0d0d0d]"
                : "text-[rgba(13,13,13,0.50)] hover:text-[#0a7cff]"
            }`}
          >
            {editMode ? <Eye size={11} /> : <Edit2 size={11} />}
            {editMode ? "Просмотр" : "Редактировать"}
          </button>
        )}
        {onClose && (
          <button onClick={onClose} className="rounded p-0.5 text-[rgba(13,13,13,0.38)] hover:text-[#0d0d0d] transition-colors">
            <X size={13} />
          </button>
        )}
      </div>

      {/* Editor area */}
      <div className="flex-1 overflow-auto min-h-0">
        <CodeMirrorEditor
          value={content}
          onChange={editMode ? setContent : undefined}
          readOnly={!editMode}
          height="100%"
          theme="light"
          extensions={[]}
          basicSetup={{
            lineNumbers: true,
            foldGutter: true,
            highlightActiveLine: editMode,
            autocompletion: false,
          }}
          style={{ fontSize: 12, height: "100%" }}
        />
      </div>

      {/* Commit panel — only in edit mode with dirty state */}
      {editMode && dirty && onCommit && (
        <div className="shrink-0 border-t border-[rgba(13,13,13,0.10)] bg-white px-3 py-2.5">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={commitMsg}
              onChange={(e) => setCommitMsg(e.target.value)}
              placeholder="Сообщение коммита..."
              className="flex-1 rounded-[6px] border border-[rgba(13,13,13,0.16)] px-2.5 py-1.5 text-[12px] outline-none focus:border-[#0a7cff]"
              onKeyDown={(e) => { if (e.key === "Enter") handleCommit(); }}
            />
            <button
              onClick={handleCommit}
              disabled={!commitMsg.trim() || committing}
              className="flex items-center gap-1.5 rounded-[6px] bg-[#0a7cff] px-3 py-1.5 text-[12px] font-medium text-white disabled:opacity-50 hover:bg-[#0066ee] transition-colors"
            >
              {committing ? <Loader2 size={12} className="animate-spin" /> : <GitCommit size={12} />}
              Commit
            </button>
          </div>
          {commitErr && (
            <p className="mt-1.5 text-[11px] text-red-500">{commitErr}</p>
          )}
        </div>
      )}
    </div>
  );
}
