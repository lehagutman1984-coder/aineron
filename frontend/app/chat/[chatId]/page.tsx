"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Send, LayoutGrid, PenSquare, Code2, Copy, Check, RotateCcw, Paperclip, BookMarked, Globe, Volume2, Square, Loader, ChevronDown, ChevronRight, Settings2 } from "lucide-react";
import { MarkdownContent } from "@/components/chat/MarkdownContent";
import { AttachmentPreview, type AttachmentState } from "@/components/chat/AttachmentPreview";
import { PromptPicker } from "@/components/chat/PromptPicker";
import { VoiceButton } from "@/components/chat/VoiceButton";
import { MediaSettingsPanel } from "@/components/chat/MediaSettingsPanel";
import { getChat, sendMessage, getMessageStatus, streamMessage, regenerateChat, uploadFile, synthesizeSpeech, APIError } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";
import type { WebMessage, ChatDetail, UiSection } from "@/lib/api/types";

const POLL_INTERVAL = 800;

const detectHTML = (s: string) =>
  /<(pre|code|div|p|ul|ol|h[1-6]|blockquote|table|img|br|video)\b/i.test(s);

export default function ChatPage() {
  const { chatId } = useParams<{ chatId: string }>();
  const id = Number(chatId);
  const qc = useQueryClient();
  const { setStars } = useAuthStore();

  const [text, setText] = useState("");
  const [showPromptPicker, setShowPromptPicker] = useState(false);
  const [attachments, setAttachments] = useState<AttachmentState[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [webSearch, setWebSearch] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("web_search_enabled") === "1";
  });

  // Настройки медиа-моделей (video/image): инициализируются из config_json.api_defaults
  const [mediaSettings, setMediaSettings] = useState<Record<string, unknown>>({});
  const [showMediaSettings, setShowMediaSettings] = useState(false);

  // Polling state (used for fal-ai image models)
  const [pendingMessageId, setPendingMessageId] = useState<number | null>(null);

  // SSE streaming state (used for text models)
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [streamingAssistId, setStreamingAssistId] = useState<number | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  // Web search two-step state
  const [searchPhase, setSearchPhase] = useState<"idle" | "searching" | "generating">("idle");
  const [liveSearchPreview, setLiveSearchPreview] = useState("");

  const animatedIds = useRef<Set<number>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data: chat, isLoading, error } = useQuery<ChatDetail>({
    queryKey: ["chat", id],
    queryFn: () => getChat(id),
    staleTime: 0,
    retry: 1,
  });

  // Polling query — only active for fal-ai image models
  const { data: polledMessage } = useQuery<WebMessage>({
    queryKey: ["message-status", pendingMessageId],
    queryFn: () => getMessageStatus(pendingMessageId!),
    enabled: pendingMessageId !== null,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || data.status === "pending") return POLL_INTERVAL;
      return false;
    },
  });

  // Инициализируем настройки медиа-модели из api_defaults при загрузке чата
  useEffect(() => {
    if (!chat) return;
    const apiDefaults = chat.network.config_json?.api_defaults;
    if (apiDefaults && typeof apiDefaults === "object") {
      setMediaSettings(apiDefaults as Record<string, unknown>);
    }
  }, [chat?.network.id]);

  useEffect(() => {
    if (!polledMessage || polledMessage.status === "pending") return;
    setPendingMessageId(null);
    if (polledMessage.status === "completed") {
      animatedIds.current.add(polledMessage.id);
    }
    qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        messages: prev.messages.map((m) =>
          m.id === polledMessage.id ? polledMessage : m
        ),
      };
    });
  }, [polledMessage, id, qc]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat?.messages, polledMessage, streamText]);

  // Mutation for fal-ai image/video models (uses polling)
  const sendMutation = useMutation({
    mutationFn: ({ msg, attachmentIds, ws, settings }: { msg: string; attachmentIds: string[]; ws: boolean; settings?: Record<string, unknown> }) =>
      sendMessage(id, { message: msg, attachment_ids: attachmentIds, web_search: ws, settings }),
    onMutate: async ({ msg }) => {
      const now = Date.now();
      qc.setQueryData<ChatDetail>(["chat", id], (prev) =>
        prev
          ? {
              ...prev,
              messages: [
                ...prev.messages,
                { id: now, role: "user", content: msg, plain_text: msg, files: [], status: "completed", error_message: null, created_at: new Date().toISOString() },
                { id: now + 1, role: "assistant", content: "", plain_text: null, files: [], status: "pending", error_message: null, created_at: new Date().toISOString() },
              ],
            }
          : prev
      );
      setText("");
      clearAttachments();
      if (textareaRef.current) textareaRef.current.style.height = "auto";
    },
    onSuccess: (res) => {
      setStars(res.new_balance);
      setPendingMessageId(res.assistant_message_id);
      qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: [
            ...prev.messages.slice(0, -1),
            { id: res.assistant_message_id, role: "assistant" as const, content: "", plain_text: null, files: [], status: "pending" as const, error_message: null, created_at: new Date().toISOString() },
          ],
        };
      });
    },
    onError: () => {
      qc.invalidateQueries({ queryKey: ["chat", id] });
    },
  });

  // Regenerate mutation — resets last assistant message, re-runs AI via Celery polling
  const regenerateMutation = useMutation({
    mutationFn: () => regenerateChat(id),
    onMutate: () => {
      qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
        if (!prev) return prev;
        const msgs = [...prev.messages];
        for (let i = msgs.length - 1; i >= 0; i--) {
          if (msgs[i].role === "assistant") {
            msgs[i] = { ...msgs[i], content: "", plain_text: null, status: "pending", error_message: null };
            break;
          }
        }
        return { ...prev, messages: msgs };
      });
    },
    onSuccess: (res) => {
      setStars(res.new_balance);
      setPendingMessageId(res.assistant_message_id);
    },
    onError: () => {
      qc.invalidateQueries({ queryKey: ["chat", id] });
    },
  });

  // Handler for text models — real SSE streaming
  const handleStreamSubmit = useCallback(
    async (msg: string, attachmentIds: string[] = []) => {
      setIsStreaming(true);
      setStreamText("");
      setStreamError(null);
      const now = Date.now();
      const tempUserId = now;
      const tempAssistId = now + 1;

      // Optimistic UI
      qc.setQueryData<ChatDetail>(["chat", id], (prev) =>
        prev
          ? {
              ...prev,
              messages: [
                ...prev.messages,
                { id: tempUserId, role: "user", content: msg, plain_text: msg, files: [], status: "completed", error_message: null, created_at: new Date().toISOString() },
                { id: tempAssistId, role: "assistant", content: "", plain_text: null, files: [], status: "pending", error_message: null, created_at: new Date().toISOString() },
              ],
            }
          : prev
      );
      setText("");
      clearAttachments();
      if (textareaRef.current) textareaRef.current.style.height = "auto";

      let realAssistId = tempAssistId;

      try {
        // Показываем "Ищу в интернете..." сразу при отправке (поиск синхронный на backend)
        if (webSearch) setSearchPhase("searching");
        await streamMessage(id, { message: msg, attachment_ids: attachmentIds, web_search: webSearch }, {
          onInit: ({ user_message_id, assistant_message_id, new_balance }) => {
            realAssistId = assistant_message_id;
            setStars(new_balance);
            setStreamingAssistId(assistant_message_id);
            qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
              if (!prev) return prev;
              return {
                ...prev,
                messages: prev.messages.map((m) => {
                  if (m.id === tempUserId) return { ...m, id: user_message_id };
                  if (m.id === tempAssistId) return { ...m, id: assistant_message_id };
                  return m;
                }),
              };
            });
          },
          onSearchDone: (preview) => {
            setLiveSearchPreview(preview);
            setSearchPhase(preview ? "generating" : "idle");
          },
          onToken: (token) => {
            setSearchPhase("idle");
            setStreamText((prev) => prev + token);
          },
          onDone: ({ content, plain_text, search_context }) => {
            qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
              if (!prev) return prev;
              return {
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === realAssistId
                    ? { ...m, content, plain_text, status: "completed" as const, search_context: search_context ?? "" }
                    : m
                ),
              };
            });
            setIsStreaming(false);
            setStreamText("");
            setStreamingAssistId(null);
            setSearchPhase("idle");
            setLiveSearchPreview("");
          },
          onError: (errorMsg) => {
            qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
              if (!prev) return prev;
              return {
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === realAssistId
                    ? { ...m, status: "failed" as const, error_message: errorMsg }
                    : m
                ),
              };
            });
            setIsStreaming(false);
            setStreamText("");
            setStreamingAssistId(null);
            setSearchPhase("idle");
            setLiveSearchPreview("");
            setStreamError(errorMsg);
          },
        });
      } catch (err) {
        const errMsg = err instanceof APIError ? err.message : "Ошибка соединения. Попробуйте ещё раз.";
        qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            messages: prev.messages.map((m) =>
              m.id === realAssistId
                ? { ...m, status: "failed" as const, error_message: errMsg }
                : m
            ),
          };
        });
        setIsStreaming(false);
        setStreamText("");
        setStreamingAssistId(null);
        setStreamError(errMsg);
      }
    },
    [id, qc, setStars, webSearch]
  );

  // File attachment upload
  const handleFiles = useCallback(
    async (fileList: FileList | File[]) => {
      const files = Array.from(fileList);
      for (const file of files) {
        const tempId = `temp-${Date.now()}-${Math.random()}`;
        const localUrl = file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined;
        setAttachments((prev) => [
          ...prev,
          {
            id: tempId,
            url: localUrl ?? "",
            filename: file.name,
            media_type: file.type.startsWith("image/") ? "image" : "other",
            mime_type: file.type,
            file_size: file.size,
            uploading: true,
            localUrl,
          },
        ]);
        try {
          const result = await uploadFile(id, file);
          setAttachments((prev) =>
            prev.map((a) => (a.id === tempId ? { ...result, localUrl } : a))
          );
        } catch {
          setAttachments((prev) =>
            prev.map((a) => (a.id === tempId ? { ...a, uploading: false, error: "Ошибка загрузки" } : a))
          );
        }
      }
    },
    [id]
  );

  const clearAttachments = useCallback(() => {
    setAttachments((prev) => {
      prev.forEach((a) => { if (a.localUrl) URL.revokeObjectURL(a.localUrl); });
      return [];
    });
  }, []);

  // Drag & drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);
  const handleDragLeave = useCallback((e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node)) setIsDragOver(false);
  }, []);
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (e.dataTransfer.files.length > 0) handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const isPending = pendingMessageId !== null;
  const isBusy = isPending || sendMutation.isPending || isStreaming || regenerateMutation.isPending;

  // Click on starter prompt card → immediate submit (no attachments)
  const handlePrompt = useCallback(
    (prompt: string) => {
      if (isBusy) return;
      if (chat?.network.provider === "fal-ai") {
        sendMutation.mutate({ msg: prompt, attachmentIds: [], ws: false });
      } else {
        handleStreamSubmit(prompt, []);
      }
    },
    [isBusy, chat?.network.provider, sendMutation, handleStreamSubmit]
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const msg = text.trim();
    const hasUploading = attachments.some((a) => a.uploading);
    if ((!msg && attachments.filter((a) => !a.error && !a.uploading).length === 0) || isBusy || hasUploading) return;
    const attachmentIds = attachments.filter((a) => !a.uploading && !a.error).map((a) => a.id);
    if (chat?.network.provider === "fal-ai") {
      sendMutation.mutate({ msg: msg || " ", attachmentIds, ws: webSearch, settings: Object.keys(mediaSettings).length > 0 ? mediaSettings : undefined });
    } else {
      handleStreamSubmit(msg || " ", attachmentIds);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  const autoResize = () => {
    const t = textareaRef.current;
    if (!t) return;
    t.style.height = "auto";
    t.style.height = Math.min(t.scrollHeight, 200) + "px";
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <BouncingDots />
      </div>
    );
  }

  if (error || !chat) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <p className="text-[15px] text-[rgba(13,13,13,0.55)]">Чат не найден</p>
        <Link href="/models/" className="text-[13px] text-[#0a7cff] hover:underline">
          К каталогу моделей
        </Link>
      </div>
    );
  }

  const displayError =
    streamError ??
    (sendMutation.error instanceof APIError ? (sendMutation.error as APIError).message : null);

  return (
    <div
      className="flex h-full flex-col"
      style={{ background: "var(--chat-page-bg)" }}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Drag overlay */}
      {isDragOver && (
        <div className="pointer-events-none absolute inset-0 z-30 flex items-center justify-center rounded-[14px] border-2 border-dashed border-[#0a7cff] bg-[rgba(10,124,255,0.06)]">
          <p className="text-[15px] font-medium text-[#0a7cff]">Отпустите для загрузки</p>
        </div>
      )}
      {/* Header */}
      <header
        className="flex h-12 shrink-0 items-center justify-between px-4"
        style={{
          background: "var(--chat-surface)",
          borderBottom: "1px solid var(--chat-header-border)",
        }}
      >
        <div className="flex min-w-0 items-center gap-2">
          {chat.network.avatar ? (
            <img
              src={chat.network.avatar}
              alt=""
              width={22}
              height={22}
              className="shrink-0 rounded-[5px]"
            />
          ) : (
            <div className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-[5px] bg-[rgba(10,124,255,0.12)] text-[#0a7cff]">
              <Code2 size={12} />
            </div>
          )}
          <span className="truncate text-[13px] font-semibold text-[#0d0d0d]">
            {chat.network.name}
          </span>
        </div>

        <div className="flex items-center gap-1">
          <Link
            href="/models/"
            className="flex h-8 items-center gap-1.5 rounded-[7px] px-2.5 text-[12px] font-medium text-[rgba(13,13,13,0.55)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d]"
          >
            <LayoutGrid size={13} />
            <span className="hidden sm:inline">Каталог</span>
          </Link>
          <Link
            href={`/models/${chat.network.slug}/`}
            className="flex h-8 items-center gap-1.5 rounded-[7px] px-2.5 text-[12px] font-medium text-white transition-colors"
            style={{ background: "#0d0d0d" }}
          >
            <PenSquare size={13} />
            <span className="hidden sm:inline">Новый чат</span>
          </Link>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-4 py-8">
          {chat.messages.length === 0 && (
            <div className="flex flex-col items-center pt-14 pb-4 text-center">
              {/* Model avatar */}
              {chat.network.avatar ? (
                <img
                  src={chat.network.avatar}
                  alt=""
                  width={56}
                  height={56}
                  className="rounded-[14px]"
                  style={{ boxShadow: "0 4px 16px rgba(0,0,0,0.10)" }}
                />
              ) : (
                <div
                  className="flex h-[56px] w-[56px] items-center justify-center rounded-[14px] text-[#0a7cff]"
                  style={{ background: "rgba(10,124,255,0.10)" }}
                >
                  <Code2 size={26} />
                </div>
              )}

              <p className="mt-4 text-[17px] font-semibold text-[#0d0d0d] dark:text-[#ececec]">
                {chat.network.name}
              </p>
              <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.42)] dark:text-[rgba(236,236,236,0.40)]">
                Выберите тему или напишите свой вопрос
              </p>

              {/* Prompt library button */}
              <button
                onClick={() => setShowPromptPicker(true)}
                className="mt-5 flex items-center gap-1.5 rounded-[8px] border px-3.5 py-2 text-[13px] font-medium transition-colors"
                style={{ borderColor: "var(--chat-input-border)", color: "rgba(13,13,13,0.55)" }}
              >
                <BookMarked size={13} />
                Шаблоны промтов
              </button>

              {/* Starter prompt cards */}
              <div className="mt-4 grid w-full grid-cols-1 gap-2.5 sm:grid-cols-2">
                {getStarterPrompts(chat.network).map((card, i) => (
                  <button
                    key={i}
                    onClick={() => handlePrompt(card.prompt)}
                    disabled={isBusy}
                    className="group rounded-[12px] border px-4 py-3.5 text-left transition-all disabled:cursor-not-allowed disabled:opacity-40"
                    style={{
                      background: "var(--chat-surface)",
                      borderColor: "var(--chat-input-border)",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 2px 10px rgba(0,0,0,0.08)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.boxShadow = "";
                    }}
                  >
                    <p className="text-[13px] font-semibold text-[#0d0d0d] dark:text-[#ececec]">
                      {card.label}
                    </p>
                    <p className="mt-0.5 line-clamp-2 text-[12px] leading-relaxed text-[rgba(13,13,13,0.48)] dark:text-[rgba(236,236,236,0.42)]">
                      {card.prompt}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-col gap-7">
            {(() => {
              const lastAssistantId = [...chat.messages]
                .reverse()
                .find((m) => m.role === "assistant" && m.status === "completed")?.id;
              return chat.messages.map((msg) => (
                <MessageRow
                  key={msg.id}
                  message={msg}
                  networkAvatar={chat.network.avatar}
                  networkName={chat.network.name}
                  shouldAnimate={animatedIds.current.has(msg.id)}
                  streamingText={
                    msg.id === streamingAssistId && msg.role === "assistant"
                      ? streamText
                      : undefined
                  }
                  canRegenerate={!isBusy && msg.id === lastAssistantId}
                  onRegenerate={() => regenerateMutation.mutate()}
                />
              ));
            })()}
          </div>

          <div ref={bottomRef} className="h-4" />
        </div>
      </div>

      {/* Input */}
      <div className="shrink-0 px-4 pb-5 pt-2" style={{ background: "var(--chat-page-bg)" }}>
        {displayError && (
          <p className="mx-auto mb-2 max-w-2xl text-[13px] text-[#e74c3c]">
            {displayError}
          </p>
        )}

        <form onSubmit={handleSubmit} className="mx-auto max-w-2xl">
          <div
            className="relative overflow-hidden rounded-[14px] transition-all"
            style={{
              background: "var(--chat-input-bg)",
              border: "1px solid var(--chat-input-border)",
              boxShadow: "0 2px 12px rgba(0,0,0,0.07)",
            }}
          >
            <AttachmentPreview
              attachments={attachments}
              onRemove={(removeId) => setAttachments((prev) => prev.filter((a) => a.id !== removeId))}
            />
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                autoResize();
              }}
              onKeyDown={handleKeyDown}
              placeholder="Введите сообщение..."
              rows={1}
              disabled={isBusy}
              className="block w-full resize-none bg-transparent px-4 py-3.5 pr-24 text-[14px] leading-relaxed text-[#0d0d0d] outline-none disabled:opacity-50 dark:text-[#ececec] dark:placeholder:text-[rgba(236,236,236,0.35)]"
              style={{ maxHeight: "200px", caretColor: "#0a7cff" }}
            />
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf,.txt,.md,.csv,.doc,.docx,.xlsx,.json"
              className="hidden"
              onChange={(e) => { if (e.target.files) { handleFiles(e.target.files); e.target.value = ""; } }}
            />
            <button
              type="button"
              disabled={isBusy}
              onClick={() => fileInputRef.current?.click()}
              className="absolute bottom-2.5 right-[50px] flex h-9 w-9 items-center justify-center rounded-[10px] text-[rgba(13,13,13,0.4)] transition-all hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] disabled:cursor-not-allowed disabled:opacity-30 dark:text-[rgba(236,236,236,0.4)] dark:hover:bg-[rgba(255,255,255,0.08)] dark:hover:text-[#ececec]"
            >
              <Paperclip size={16} />
            </button>
            <button
              type="submit"
              disabled={(text.trim() === "" && attachments.filter((a) => !a.error && !a.uploading).length === 0) || isBusy}
              className="absolute bottom-2.5 right-2.5 flex h-9 w-9 items-center justify-center rounded-[10px] text-white transition-all disabled:cursor-not-allowed disabled:opacity-25"
              style={{ background: "#0d0d0d" }}
            >
              <Send size={15} />
            </button>
          </div>

          {/* Toolbar: web search + voice */}
          {chat.network.provider !== "fal-ai" && (
            <div className="mt-1.5 flex items-center gap-1 px-1">
              <button
                type="button"
                onClick={() => {
                  const next = !webSearch;
                  setWebSearch(next);
                  localStorage.setItem("web_search_enabled", next ? "1" : "0");
                }}
                title={
                  webSearch
                    ? "Веб-поиск включён — запрос идёт через Grok Search. Нажмите чтобы отключить"
                    : "Включить поиск в интернете (через Grok Search)"
                }
                className={[
                  "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-all",
                  webSearch
                    ? "bg-[rgba(10,124,255,0.12)] text-[#0a7cff] ring-1 ring-[rgba(10,124,255,0.35)]"
                    : "text-[rgba(13,13,13,0.45)] hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.38)] dark:hover:text-[#ececec]",
                ].join(" ")}
              >
                <Globe size={12} />
                Поиск в интернете
                {webSearch && (
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#0a7cff]" />
                )}
              </button>

              <VoiceButton
                disabled={isBusy}
                onTranscript={(t) =>
                  setText((prev) => (prev.trim() ? prev.trimEnd() + " " + t : t))
                }
              />
            </div>
          )}

          {/* Панель настроек для медиа-моделей (video/image) */}
          {chat.network.provider === "fal-ai" && chat.network.config_json?.ui_settings && (
            <div className="mt-1.5 px-1">
              <button
                type="button"
                onClick={() => setShowMediaSettings((v) => !v)}
                className={[
                  "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-all",
                  showMediaSettings
                    ? "bg-[rgba(13,13,13,0.08)] text-[#0d0d0d] dark:bg-[rgba(255,255,255,0.12)] dark:text-[#ececec]"
                    : "text-[rgba(13,13,13,0.45)] hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.38)] dark:hover:text-[#ececec]",
                ].join(" ")}
              >
                <Settings2 size={12} />
                Настройки
                <ChevronDown size={11} className={showMediaSettings ? "rotate-180 transition-transform" : "transition-transform"} />
              </button>

              {showMediaSettings && (
                <MediaSettingsPanel
                  sections={chat.network.config_json.ui_settings.sections as UiSection[]}
                  values={mediaSettings}
                  onChange={setMediaSettings}
                />
              )}
            </div>
          )}

          {isBusy && (
            <div className="mt-2 flex items-center gap-2 px-1">
              <BouncingDots />
              <span className="text-[12px] text-[rgba(13,13,13,0.42)]">
                {searchPhase === "searching" ? (
                  <span className="font-medium text-[#0a7cff]">Grok ищет в интернете...</span>
                ) : searchPhase === "generating" ? (
                  <>
                    <span className="font-medium text-[#16a34a]">Найдено</span>
                    <span className="mx-1 text-[rgba(13,13,13,0.25)]">·</span>
                    <span>{chat.network.name} анализирует...</span>
                  </>
                ) : (
                  <span>{chat.network.name} отвечает...</span>
                )}
              </span>
            </div>
          )}
        </form>
      </div>

      {/* Prompt picker modal */}
      {showPromptPicker && (
        <PromptPicker
          onSelect={(content) => {
            setText(content);
            setShowPromptPicker(false);
          }}
          onClose={() => setShowPromptPicker(false)}
        />
      )}
    </div>
  );
}

/* ─── Bouncing dots ─────────────────────────────────────── */
function BouncingDots() {
  return (
    <div className="flex gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-2 w-2 animate-bounce rounded-full"
          style={{
            background: "rgba(13,13,13,0.28)",
            animationDelay: `${i * 0.18}s`,
            animationDuration: "1.1s",
          }}
        />
      ))}
    </div>
  );
}

/* ─── Single message row ────────────────────────────────── */
function MessageRow({
  message,
  networkAvatar,
  networkName,
  shouldAnimate,
  streamingText,
  canRegenerate,
  onRegenerate,
}: {
  message: WebMessage;
  networkAvatar: string | null;
  networkName: string;
  shouldAnimate: boolean;
  streamingText?: string;
  canRegenerate?: boolean;
  onRegenerate?: () => void;
}) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[78%] rounded-[18px] rounded-br-[4px] px-4 py-3 text-[14px] leading-relaxed text-white"
          style={{ background: "var(--chat-user-bubble)" }}
        >
          <PlainText text={message.content} />
        </div>
      </div>
    );
  }

  return (
    <div className="group flex gap-3">
      {/* Model avatar */}
      <div className="shrink-0 pt-[3px]">
        {networkAvatar ? (
          <img
            src={networkAvatar}
            alt={networkName}
            width={26}
            height={26}
            className="rounded-[6px]"
          />
        ) : (
          <div
            className="flex h-[26px] w-[26px] items-center justify-center rounded-[6px] text-[#0a7cff]"
            style={{ background: "rgba(10,124,255,0.12)" }}
          >
            <Code2 size={13} />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        {/* Live streaming: show accumulated tokens with cursor */}
        {streamingText !== undefined ? (
          <StreamingDisplay text={streamingText} />
        ) : message.status === "pending" ? (
          <div className="flex items-center gap-1 py-2">
            <BouncingDots />
          </div>
        ) : message.status === "failed" ? (
          <p className="text-[14px] text-[#e74c3c]">
            {message.error_message ?? "Ошибка генерации. Попробуйте ещё раз."}
          </p>
        ) : (
          <>
            {message.search_context && (
              <SearchContextBlock context={message.search_context} />
            )}
            <AssistantContent
              content={message.content}
              plain_text={message.plain_text ?? null}
              shouldAnimate={shouldAnimate}
            />
            {/* Hover action bar */}
            <div className="mt-1.5 flex items-center gap-0.5 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
              <CopyButton plainText={message.plain_text} htmlContent={message.content} />
              {canRegenerate && onRegenerate && (
                <button
                  onClick={onRegenerate}
                  className="flex h-7 items-center gap-1.5 rounded-[6px] px-2 text-[12px] font-medium transition-colors"
                  style={{ color: "rgba(13,13,13,0.42)" }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = "rgba(13,13,13,0.06)";
                    (e.currentTarget as HTMLButtonElement).style.color = "#0d0d0d";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = "";
                    (e.currentTarget as HTMLButtonElement).style.color = "rgba(13,13,13,0.42)";
                  }}
                  title="Повторить генерацию"
                >
                  <RotateCcw size={13} />
                  <span>Ещё раз</span>
                </button>
              )}
              {(message.plain_text || message.content) && (
                <SpeakButton
                  text={message.plain_text?.slice(0, 2000) || message.content.replace(/<[^>]+>/g, " ").slice(0, 2000)}
                />
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/* ─── TTS speak button ───────────────────────────────────── */
function SpeakButton({ text }: { text: string }) {
  const [state, setState] = useState<"idle" | "loading" | "playing">("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);

  const stop = () => {
    audioRef.current?.pause();
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    audioRef.current = null;
    urlRef.current = null;
    setState("idle");
  };

  const handleClick = async () => {
    if (state === "playing") { stop(); return; }
    if (state === "loading") return;
    setState("loading");
    try {
      const blob = await synthesizeSpeech(text);
      const url = URL.createObjectURL(blob);
      urlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = stop;
      audio.onerror = stop;
      await audio.play();
      setState("playing");
    } catch {
      setState("idle");
    }
  };

  return (
    <button
      onClick={handleClick}
      className="flex h-7 items-center gap-1.5 rounded-[6px] px-2 text-[12px] font-medium transition-colors"
      style={{ color: state !== "idle" ? "#0a7cff" : "rgba(13,13,13,0.42)" }}
      onMouseEnter={(e) => {
        if (state === "idle") {
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(13,13,13,0.06)";
          (e.currentTarget as HTMLButtonElement).style.color = "#0d0d0d";
        }
      }}
      onMouseLeave={(e) => {
        if (state === "idle") {
          (e.currentTarget as HTMLButtonElement).style.background = "";
          (e.currentTarget as HTMLButtonElement).style.color = "rgba(13,13,13,0.42)";
        }
      }}
      title={state === "playing" ? "Остановить" : "Озвучить ответ (TTS)"}
    >
      {state === "loading" ? (
        <Loader size={13} className="animate-spin" />
      ) : state === "playing" ? (
        <Square size={13} />
      ) : (
        <Volume2 size={13} />
      )}
      <span>{state === "loading" ? "Загрузка..." : state === "playing" ? "Стоп" : "Озвучить"}</span>
    </button>
  );
}

/* ─── Copy button with 2s "Скопировано" state ───────────── */
function CopyButton({
  plainText,
  htmlContent,
}: {
  plainText: string | null | undefined;
  htmlContent: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const text =
      plainText ||
      htmlContent.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="flex h-7 items-center gap-1.5 rounded-[6px] px-2 text-[12px] font-medium transition-colors"
      style={{ color: copied ? "#0a7cff" : "rgba(13,13,13,0.42)" }}
      onMouseEnter={(e) => {
        if (!copied) {
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(13,13,13,0.06)";
          (e.currentTarget as HTMLButtonElement).style.color = "#0d0d0d";
        }
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.background = "";
        (e.currentTarget as HTMLButtonElement).style.color = copied
          ? "#0a7cff"
          : "rgba(13,13,13,0.42)";
      }}
      title="Скопировать"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      <span>{copied ? "Скопировано" : "Копировать"}</span>
    </button>
  );
}

/* ─── Plain text (user messages) ───────────────────────── */
function PlainText({ text }: { text: string }) {
  return (
    <>
      {text.split("\n").map((line, i, arr) => (
        <span key={i}>
          {line}
          {i < arr.length - 1 && <br />}
        </span>
      ))}
    </>
  );
}

/* ─── Live streaming display — smooth drain from token queue ─ */
function StreamingDisplay({ text }: { text: string }) {
  const [displayed, setDisplayed] = useState("");
  // queue of chars received but not yet shown
  const queueRef = useRef("");
  // how many chars of `text` we've already enqueued
  const enqueuedRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  // Feed new chars into queue whenever accumulated text grows
  useEffect(() => {
    if (text.length > enqueuedRef.current) {
      queueRef.current += text.slice(enqueuedRef.current);
      enqueuedRef.current = text.length;
    }
  }, [text]);

  // Drain queue every animation frame at a smooth, adaptive rate
  useEffect(() => {
    function drain() {
      const pending = queueRef.current.length;
      if (pending > 0) {
        // Adaptive speed: slow for small queue (smooth), fast for large queue (catch-up)
        const take = pending < 15 ? 1 : pending < 60 ? 3 : 7;
        setDisplayed((p) => p + queueRef.current.slice(0, take));
        queueRef.current = queueRef.current.slice(take);
      }
      rafRef.current = requestAnimationFrame(drain);
    }
    rafRef.current = requestAnimationFrame(drain);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, []); // mount once

  return (
    <div
      className="text-[15px] leading-[1.75]"
      style={{ color: "rgba(13,13,13,0.86)" }}
    >
      <PlainText text={displayed || " "} />
      <span
        className="ml-0.5 inline-block animate-pulse"
        style={{
          width: "2px",
          height: "1.1em",
          background: "#0a7cff",
          verticalAlign: "text-bottom",
          borderRadius: "1px",
        }}
      />
    </div>
  );
}

/* ─── Completed assistant content ───────────────────────── */
function AssistantContent({
  content,
  plain_text,
  shouldAnimate,
}: {
  content: string;
  plain_text: string | null;
  shouldAnimate: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Attach copy handlers to Django CodeFormatter buttons (legacy HTML path).
  // Must be before any early return to satisfy rules-of-hooks.
  useEffect(() => {
    if (!containerRef.current) return;
    const buttons = containerRef.current.querySelectorAll<HTMLButtonElement>(".copy-code");
    buttons.forEach((btn) => {
      if (btn.dataset.bound) return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => {
        const block = btn.closest(".code-block");
        const code = block?.querySelector("code")?.textContent ?? "";
        navigator.clipboard.writeText(code).catch(() => {});
        const orig = btn.textContent ?? "Копировать";
        btn.textContent = "Скопировано";
        setTimeout(() => { btn.textContent = orig; }, 2000);
      });
    });
  }, [content]);

  // Prefer plain_text (raw markdown) → render with react-markdown.
  // Skip if plain_text is itself HTML — fal-ai stores HTML (with <img>) in plain_text.
  if (plain_text && !detectHTML(plain_text)) {
    return <MarkdownContent content={plain_text} />;
  }

  // HTML path: CodeFormatter output for text models, or <img> HTML from fal-ai image models.
  // Use content (formatted HTML) if it has HTML, otherwise fall back to plain_text.
  const htmlSource = detectHTML(content) ? content : (plain_text ?? content);
  const html = detectHTML(htmlSource);

  if (html) {
    return (
      <div
        ref={containerRef}
        className="chat-prose"
        dangerouslySetInnerHTML={{ __html: htmlSource }}
      />
    );
  }

  // Plain text with optional typewriter for image-model text responses
  return <PlainTextAnimated content={content} shouldAnimate={shouldAnimate} />;
}

function PlainTextAnimated({ content, shouldAnimate }: { content: string; shouldAnimate: boolean }) {
  const doAnimate = useRef(shouldAnimate && content.length > 0);
  const [displayed, setDisplayed] = useState(doAnimate.current ? "" : content);
  const [showCursor, setShowCursor] = useState(doAnimate.current);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!doAnimate.current) return;
    let i = 0;
    const delay = Math.max(5, Math.min(20, 1500 / content.length));
    const timer = setInterval(() => {
      i++;
      setDisplayed(content.slice(0, i));
      if (i >= content.length) {
        clearInterval(timer);
        setShowCursor(false);
      }
    }, delay);
    return () => clearInterval(timer);
  }, []); // intentionally runs once on mount — content is captured via closure at mount time

  return (
    <div className="text-[15px] leading-[1.75]" style={{ color: "rgba(13,13,13,0.86)" }}>
      <PlainText text={displayed} />
      {showCursor && (
        <span
          className="ml-0.5 inline-block animate-pulse"
          style={{ width: "2px", height: "1.1em", background: "#0a7cff", verticalAlign: "text-bottom", borderRadius: "1px" }}
        />
      )}
    </div>
  );
}

/* ─── Search context block ───────────────────────────────── */
function SearchContextBlock({ context }: { context: string }) {
  const [open, setOpen] = useState(false);
  const lines = context.split("\n").filter(Boolean);
  const preview = lines.slice(0, 3).join("\n");

  return (
    <div className="mb-3 rounded-[10px] border border-[rgba(10,124,255,0.18)] bg-[rgba(10,124,255,0.04)]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        <Globe size={13} className="shrink-0 text-[#0a7cff]" />
        <span className="flex-1 text-[12px] font-medium text-[#0a7cff]">
          Что нашёл Grok Search
        </span>
        {open ? (
          <ChevronDown size={13} className="shrink-0 text-[rgba(10,124,255,0.6)]" />
        ) : (
          <ChevronRight size={13} className="shrink-0 text-[rgba(10,124,255,0.6)]" />
        )}
      </button>
      <div className="border-t border-[rgba(10,124,255,0.12)] px-3 pb-3 pt-2">
        <pre className="whitespace-pre-wrap font-sans text-[12px] leading-relaxed text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.55)]">
          {open ? context : preview + (lines.length > 3 ? "\n..." : "")}
        </pre>
        {!open && lines.length > 3 && (
          <button
            onClick={() => setOpen(true)}
            className="mt-1 text-[11px] text-[rgba(10,124,255,0.7)] hover:text-[#0a7cff]"
          >
            Показать всё ({lines.length} строк)
          </button>
        )}
      </div>
    </div>
  );
}

/* ─── Starter prompts ────────────────────────────────────── */
type PromptCard = { label: string; prompt: string };

function getStarterPrompts(network: { provider: string; category: { name: string; slug: string } | null }): PromptCard[] {
  // Image generation models
  if (network.provider === "fal-ai") {
    return [
      { label: "Пейзаж", prompt: "Реалистичное фото горного рассвета: туман над долиной, золотой час, высокое разрешение" },
      { label: "Портрет", prompt: "Портрет молодой женщины в стиле арт-деко, детализированный, мягкое студийное освещение" },
      { label: "Абстракция", prompt: "Абстрактная цифровая живопись в синих и фиолетовых тонах с неоновыми акцентами" },
      { label: "Интерьер", prompt: "Уютная библиотека с высокими деревянными полками, тёплый свет, кресло у панорамного окна" },
    ];
  }

  // Category-specific prompts
  const cat = (network.category?.slug ?? network.category?.name ?? "").toLowerCase();

  if (cat.includes("kod") || cat.includes("code") || cat.includes("програм") || cat.includes("разраб")) {
    return [
      { label: "Написать функцию", prompt: "Напиши функцию на Python, которая проверяет, является ли строка палиндромом, с тестами" },
      { label: "Найти баг", prompt: "Найди и исправь баг в этом коде:\n\n```python\n# вставь код сюда\n```" },
      { label: "SQL запрос", prompt: "Напиши SQL-запрос: топ-10 пользователей по количеству заказов за последние 30 дней" },
      { label: "Code review", prompt: "Сделай code review этого кода и предложи улучшения по производительности и читаемости:" },
    ];
  }

  if (cat.includes("перевод") || cat.includes("translat")) {
    return [
      { label: "На английский", prompt: "Переведи следующий текст на английский язык, сохранив стиль и тон:" },
      { label: "На русский", prompt: "Translate the following text to Russian, keeping the original style:" },
      { label: "Деловой стиль", prompt: "Переведи на английский в деловом стиле для международного письма:" },
      { label: "Проверь перевод", prompt: "Проверь этот перевод и исправь ошибки, объясни каждое исправление:" },
    ];
  }

  // General text model prompts
  return [
    { label: "Объяснение", prompt: "Объясни, как работает квантовое шифрование, простыми словами без технических терминов" },
    { label: "Написать код", prompt: "Напиши Python-скрипт, который парсит JSON-файл и выводит топ-5 записей по полю \"score\"" },
    { label: "Составить текст", prompt: "Помоги написать профессиональное письмо с предложением о партнёрстве — кратко и убедительно" },
    { label: "Анализ", prompt: "Составь SWOT-анализ для небольшого онлайн-сервиса с подпиской и AI-функциями" },
  ];
}

// MediaSettingsPanel is imported from @/components/chat/MediaSettingsPanel
