"use client";

import { X, FileText, File, FileCode, Loader2, AlertCircle } from "lucide-react";

export type AttachmentState = {
  id: string;
  url: string;
  filename: string;
  media_type: string;
  mime_type: string;
  file_size: number;
  uploading?: boolean;
  error?: string;
  localUrl?: string;
};

export function AttachmentPreview({
  attachments,
  onRemove,
}: {
  attachments: AttachmentState[];
  onRemove: (id: string) => void;
}) {
  if (attachments.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 px-4 pt-3 pb-1">
      {attachments.map((att) => (
        <AttachmentChip key={att.id} attachment={att} onRemove={() => onRemove(att.id)} />
      ))}
    </div>
  );
}

function AttachmentChip({
  attachment,
  onRemove,
}: {
  attachment: AttachmentState;
  onRemove: () => void;
}) {
  const imgSrc =
    attachment.media_type === "image" ? attachment.localUrl || attachment.url : null;

  return (
    <div
      className="relative flex min-w-0 max-w-[180px] items-center gap-2 overflow-hidden rounded-[10px] border pr-2 transition-shadow"
      style={{
        background: "var(--chat-surface)",
        borderColor: "var(--chat-input-border)",
      }}
    >
      {/* Thumbnail for images, icon for other files */}
      {imgSrc ? (
        <img
          src={imgSrc}
          alt={attachment.filename}
          className="h-10 w-10 shrink-0 object-cover"
          style={{ borderRadius: "10px 0 0 10px" }}
        />
      ) : (
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center"
          style={{ background: "rgba(10,124,255,0.07)", borderRadius: "10px 0 0 10px" }}
        >
          <FileTypeIcon mime={attachment.mime_type} />
        </div>
      )}

      {/* Name + size */}
      <div className="min-w-0 flex-1 py-1.5">
        {attachment.uploading ? (
          <div className="flex items-center gap-1.5 text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
            <Loader2 size={11} className="animate-spin" />
            Загрузка...
          </div>
        ) : attachment.error ? (
          <div className="flex items-center gap-1 text-[11px] text-[#e74c3c]">
            <AlertCircle size={11} />
            Ошибка
          </div>
        ) : (
          <p className="truncate text-[11px] font-medium text-[#1A1A1A] dark:text-[#EDE8E3]">
            {attachment.filename}
          </p>
        )}
        <p className="text-[10px] text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.32)]">
          {formatBytes(attachment.file_size)}
        </p>
      </div>

      {/* Remove */}
      <button
        onClick={onRemove}
        className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-[rgba(13,13,13,0.08)] dark:hover:bg-[rgba(255,255,255,0.10)]"
        title="Удалить"
      >
        <X size={11} className="text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.45)]" />
      </button>
    </div>
  );
}

function FileTypeIcon({ mime }: { mime: string }) {
  if (mime === "application/pdf")
    return <FileText size={17} style={{ color: "#e74c3c" }} />;
  if (
    mime.startsWith("text/") ||
    mime === "application/json" ||
    mime.includes("javascript") ||
    mime.includes("typescript")
  )
    return <FileCode size={17} style={{ color: "#D97757" }} />;
  return <File size={17} style={{ color: "#D97757" }} />;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}
