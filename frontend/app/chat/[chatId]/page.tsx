"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Send, LayoutGrid, PenSquare, Code2, Copy, Check, RotateCcw, Paperclip, BookMarked, Globe, Volume2, Square, Loader, ChevronDown, ChevronRight, Settings2, FileText, X, GitCommit, CheckCircle2, XCircle, Download, Layers, BookmarkPlus, GitBranch, Microscope, Brain, ImagePlus, Pencil, Loader2, Film, Maximize2, Images, Palette } from "lucide-react";
import { MarkdownContent } from "@/components/chat/MarkdownContent";
import { AttachmentPreview, type AttachmentState } from "@/components/chat/AttachmentPreview";
import { PromptPicker } from "@/components/chat/PromptPicker";
import { VoiceButton } from "@/components/chat/VoiceButton";
import { MediaSettingsPanel } from "@/components/chat/MediaSettingsPanel";
import { ArtifactPanel, extractArtifact, type Artifact } from "@/components/chat/ArtifactPanel";
import { ResponseVariants } from "@/components/chat/ResponseVariants";
import { DeepResearchPanel } from "@/components/chat/DeepResearchPanel";
import { ResearchReport } from "@/components/chat/ResearchReport";
import { MemoryToast } from "@/components/chat/MemoryToast";
import { ForgetMemoryPanel } from "@/components/chat/ForgetMemoryPanel";
import { EditImageModal, type EditImagePayload } from "@/components/chat/EditImageModal";
import { AnimateImageModal } from "@/components/chat/AnimateImageModal";
import { GenerationProgress } from "@/components/chat/GenerationProgress";
import { PromptEnhancer } from "@/components/chat/PromptEnhancer";
import { getChat, sendMessage, getMessageStatus, streamMessage, regenerateChat, uploadFile, synthesizeSpeech, confirmCommit, exportChat, quickSaveFact, branchChat, startDeepResearch, getResearchStatus, getMemoryToast, upscaleGeneration, createVariations, APIError, type CommitProposed } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";
import { useUIStore } from "@/lib/stores/ui";
import type { WebMessage, ChatDetail, UiSection, KBSource } from "@/lib/api/types";

const POLL_INTERVAL = 800;

const detectHTML = (s: string) =>
  /<(pre|code|div|p|ul|ol|h[1-6]|blockquote|table|img|br|video)\b/i.test(s);

// img2img: извлечь URL первого сгенерированного изображения из HTML сообщения
const extractFirstImageUrl = (html: string): string | null => {
  const m = /<img[^>]+src=["']([^"']+)["']/i.exec(html || "");
  return m ? m[1] : null;
};

export default function ChatPage() {
  const { chatId } = useParams<{ chatId: string }>();
  const id = Number(chatId);
  const qc = useQueryClient();
  const { setStars } = useAuthStore();
  const addToast = useUIStore((s) => s.addToast);

  const [text, setText] = useState("");
  const [showPromptPicker, setShowPromptPicker] = useState(false);
  const [attachments, setAttachments] = useState<AttachmentState[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // img2img: исходное изображение для редактирования (только для fal-ai моделей)
  const [sourceImage, setSourceImage] = useState<{ url: string; localUrl: string; uploading: boolean; error?: boolean } | null>(null);
  const sourceInputRef = useRef<HTMLInputElement>(null);
  // img2img: модалка редактирования (маска / outpaint) для сгенерированного изображения
  const [editModalUrl, setEditModalUrl] = useState<string | null>(null);
  // img2video: модалка "Оживить" — выбор видео-модели для сгенерированного изображения
  const [animateModalUrl, setAnimateModalUrl] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [webSearch, setWebSearch] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("web_search_enabled") === "1";
  });
  const [variantsMode, setVariantsMode] = useState(false);
  const [researchMode, setResearchMode] = useState(false);
  const [activeResearchId, setActiveResearchId] = useState<number | null>(null);
  const [activeResearchMsgId, setActiveResearchMsgId] = useState<number | null>(null);
  const [memoryToast, setMemoryToast] = useState<{ count: number; facts: string[] } | null>(null);

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

  // AI-коммит из чата (Sprint 4.3)
  const [pendingCommit, setPendingCommit] = useState<CommitProposed | null>(null);
  const [commitActionLoading, setCommitActionLoading] = useState(false);

  const [activeArtifact, setActiveArtifact] = useState<Artifact | null>(null);

  const animatedIds = useRef<Set<number>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [instructionsDismissed, setInstructionsDismissed] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

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

  // Sprint 2 — deep research polling
  const { data: researchPoll } = useQuery({
    queryKey: ["deep-research", activeResearchId],
    queryFn: () => getResearchStatus(activeResearchId!),
    enabled: activeResearchId !== null,
    refetchInterval: (query) => {
      const st = query.state.data?.status;
      if (st === "done" || st === "error") return false;
      return 2000;
    },
  });

  // Plan Gap 1: restore research polling after page reload (close-tab resume)
  useEffect(() => {
    if (!chat?.messages || activeResearchId !== null) return;
    const inFlight = chat.messages.find(
      (m) => m.is_research && m.status === "pending" && m.research_id
    );
    if (inFlight) {
      setActiveResearchId(inFlight.research_id!);
      setActiveResearchMsgId(inFlight.id);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat?.id]);

  // Sprint 3: запускаем polling для fal-ai сообщения «в работе» при загрузке/навигации.
  // Нужно для img2video (переход из "Оживить" в новый чат) и для перезагрузки страницы
  // во время генерации — иначе статус не опрашивается и прогресс/результат не появятся.
  useEffect(() => {
    if (!chat?.messages || pendingMessageId !== null) return;
    if (chat.network.provider !== "fal-ai") return;
    const pendingMsg = [...chat.messages]
      .reverse()
      .find((m) => m.role === "assistant" && m.status === "pending");
    if (pendingMsg) setPendingMessageId(pendingMsg.id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat?.id]);

  useEffect(() => {
    if (!researchPoll || !activeResearchMsgId) return;
    if (researchPoll.status === "done" && researchPoll.content) {
      qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: prev.messages.map((m) =>
            m.id === activeResearchMsgId
              ? { ...m, content: researchPoll.content!, plain_text: researchPoll.plain_text ?? "", status: "completed" as const, is_research: true }
              : m
          ),
        };
      });
      setActiveResearchId(null);
      setActiveResearchMsgId(null);
    }
    if (researchPoll.status === "error") {
      setActiveResearchId(null);
      setActiveResearchMsgId(null);
    }
  }, [researchPoll?.status, researchPoll?.content, activeResearchMsgId, id, qc]);

  // Инициализируем настройки медиа-модели из api_defaults при загрузке чата
  useEffect(() => {
    if (!chat) return;
    const apiDefaults = chat.network.config_json?.api_defaults;
    if (apiDefaults && typeof apiDefaults === "object") {
      setMediaSettings(apiDefaults as Record<string, unknown>);
    }
  }, [chat?.network.id]);

  useEffect(() => {
    if (!polledMessage) return;
    // Пока сообщение ещё в работе — пробрасываем generation_id в данные чата,
    // чтобы смонтировался прогресс-бар видео (не меняя статус pending).
    if (polledMessage.status === "pending") {
      if (polledMessage.generation_id) {
        qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            messages: prev.messages.map((m) =>
              m.id === polledMessage.id && m.generation_id !== polledMessage.generation_id
                ? { ...m, generation_id: polledMessage.generation_id }
                : m
            ),
          };
        });
      }
      return;
    }
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
    if (!isNearBottomRef.current) return;
    const el = scrollContainerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
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
      setSourceImage((prev) => { if (prev?.localUrl?.startsWith("blob:")) URL.revokeObjectURL(prev.localUrl); return null; });
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
        await streamMessage(id, { message: msg, attachment_ids: attachmentIds, web_search: webSearch, variants_mode: variantsMode }, {
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
          onDone: ({ content, plain_text, search_context, sources, variants, commit_proposed, used_memory }) => {
            qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
              if (!prev) return prev;
              return {
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === realAssistId
                    ? { ...m, content, plain_text, status: "completed" as const, search_context: search_context ?? "", kb_sources: sources ?? m.kb_sources, variants: variants ?? m.variants, used_memory: used_memory ?? false }
                    : m
                ),
              };
            });
            setIsStreaming(false);
            setStreamText("");
            setStreamingAssistId(null);
            setSearchPhase("idle");
            setLiveSearchPreview("");
            if (commit_proposed) setPendingCommit(commit_proposed);
            // Sprint 4: poll for memory toast ~3s after done (Celery task runs async)
            setTimeout(() => {
              getMemoryToast().then((d) => {
                if (d.count > 0) setMemoryToast(d);
              }).catch(() => undefined);
            }, 3000);
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
    [id, qc, setStars, webSearch, variantsMode]
  );

  // Sprint 2 — Deep Research submit
  const handleResearchSubmit = useCallback(
    async (question: string) => {
      if (!question.trim()) return;
      const now = Date.now();
      const tempUserId = now;
      const tempAssistId = now + 1;
      qc.setQueryData<ChatDetail>(["chat", id], (prev) =>
        prev
          ? {
              ...prev,
              messages: [
                ...prev.messages,
                { id: tempUserId, role: "user", content: question, plain_text: question, files: [], status: "completed", error_message: null, created_at: new Date().toISOString() },
                { id: tempAssistId, role: "assistant", content: "", plain_text: null, files: [], status: "pending", error_message: null, created_at: new Date().toISOString() },
              ],
            }
          : prev
      );
      try {
        const res = await startDeepResearch(id, question);
        // Replace temp IDs with real ones
        qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            messages: prev.messages
              .filter((m) => m.id !== tempUserId && m.id !== tempAssistId)
              .concat([
                { id: res.user_message_id, role: "user", content: question, plain_text: question, files: [], status: "completed", error_message: null, created_at: new Date().toISOString() },
                { id: res.message_id, role: "assistant", content: "", plain_text: null, files: [], status: "pending", error_message: null, is_research: true, research_id: res.research_id, created_at: new Date().toISOString() },
              ]),
          };
        });
        setActiveResearchId(res.research_id);
        setActiveResearchMsgId(res.message_id);
      } catch (e) {
        qc.setQueryData<ChatDetail>(["chat", id], (prev) =>
          prev ? { ...prev, messages: prev.messages.filter((m) => m.id !== tempUserId && m.id !== tempAssistId) } : prev
        );
      }
    },
    [id, qc]
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

  // img2img: загрузка исходного изображения для редактирования
  const handleSourceImage = useCallback(
    async (file: File) => {
      const localUrl = URL.createObjectURL(file);
      setSourceImage((prev) => { if (prev?.localUrl?.startsWith("blob:")) URL.revokeObjectURL(prev.localUrl); return { url: "", localUrl, uploading: true }; });
      try {
        const result = await uploadFile(id, file);
        setSourceImage({ url: result.url, localUrl, uploading: false });
      } catch {
        setSourceImage({ url: "", localUrl, uploading: false, error: true });
      }
    },
    [id]
  );

  const clearSourceImage = useCallback(() => {
    setSourceImage((prev) => { if (prev?.localUrl?.startsWith("blob:")) URL.revokeObjectURL(prev.localUrl); return null; });
  }, []);

  // img2img: "Редактировать" из пузыря сообщения — открывает модалку (маска / outpaint)
  const handleEditImage = useCallback((url: string) => {
    setEditModalUrl(url);
  }, []);

  // img2video: "Оживить" из пузыря сообщения — открывает модалку выбора видео-модели
  const handleAnimateImage = useCallback((url: string) => {
    setAnimateModalUrl(url);
  }, []);

  // Видео готово (SSE) — форсируем перезагрузку статуса сообщения
  const handleVideoComplete = useCallback(() => {
    qc.invalidateQueries({ queryKey: ["message-status"] });
    qc.invalidateQueries({ queryKey: ["chat", id] });
  }, [qc, id]);

  // Sprint 6: апскейл сгенерированного изображения из пузыря сообщения
  const handleUpscaleImage = useCallback(
    async (generationId: number, factor: 2 | 4) => {
      try {
        const res = await upscaleGeneration(String(generationId), factor);
        addToast({
          type: "success",
          message: `Апскейл ×${res.factor} запущен. Результат появится в «Мои файлы» через минуту.`,
        });
      } catch (err) {
        addToast({
          type: "error",
          message: err instanceof APIError ? err.message : "Не удалось запустить апскейл.",
        });
      }
    },
    [addToast]
  );

  // Sprint 6: вариации сгенерированного изображения из пузыря сообщения
  const handleVariationsImage = useCallback(
    async (generationId: number) => {
      try {
        await createVariations(String(generationId), 4);
        addToast({ type: "success", message: "Создаём 4 вариации — они появятся в этом чате." });
        qc.invalidateQueries({ queryKey: ["chat", id] });
      } catch (err) {
        addToast({
          type: "error",
          message: err instanceof APIError ? err.message : "Не удалось создать вариации.",
        });
      }
    },
    [addToast, qc, id]
  );

  // Sprint 6: использовать изображение как референс стиля (переход к выбору модели)
  const handleStyleImage = useCallback((url: string) => {
    try {
      localStorage.setItem("aineron_style_image", url);
    } catch {}
    window.location.href = "/models/";
  }, []);

  // img2img: применить редактирование из модалки — отправляет сообщение с image_url/mask_url/outpaint
  const handleEditModalSubmit = useCallback(
    (payload: EditImagePayload) => {
      const falSettings: Record<string, unknown> = {
        ...mediaSettings,
        image_url: payload.image_url,
      };
      if (payload.mask_url) falSettings.mask_url = payload.mask_url;
      if (payload.outpaint_direction) falSettings.outpaint_direction = payload.outpaint_direction;
      sendMutation.mutate({
        msg: payload.prompt || " ",
        attachmentIds: [],
        ws: false,
        settings: falSettings,
      });
      setEditModalUrl(null);
    },
    [mediaSettings, sendMutation]
  );

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
    const hasUploading = attachments.some((a) => a.uploading) || sourceImage?.uploading === true;
    if ((!msg && attachments.filter((a) => !a.error && !a.uploading).length === 0 && !sourceImage) || isBusy || hasUploading) return;
    if (researchMode && msg) {
      setText("");
      setAttachments([]);
      void handleResearchSubmit(msg);
      return;
    }
    const attachmentIds = attachments.filter((a) => !a.uploading && !a.error).map((a) => a.id);
    if (chat?.network.provider === "fal-ai") {
      const falSettings: Record<string, unknown> = { ...mediaSettings };
      if (sourceImage && sourceImage.url && !sourceImage.error) {
        falSettings.image_url = sourceImage.url;
      }
      sendMutation.mutate({ msg: msg || " ", attachmentIds, ws: webSearch, settings: Object.keys(falSettings).length > 0 ? falSettings : undefined });
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

  const scrollToBottom = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    isNearBottomRef.current = true;
    setShowScrollBtn(false);
  }, []);

  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    isNearBottomRef.current = distFromBottom < 120;
    setShowScrollBtn(distFromBottom >= 120);
  }, []);

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
      className="flex h-full"
      style={{ background: "var(--chat-page-bg)", position: "relative" }}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
    {/* Main chat column */}
    <div className="flex h-full min-w-0 flex-1 flex-col">
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
          <div className="relative group/export">
            <button
              className="flex h-8 items-center gap-1.5 rounded-[7px] px-2.5 text-[12px] font-medium text-[rgba(13,13,13,0.55)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d]"
              title="Экспортировать чат"
            >
              <Download size={13} />
              <span className="hidden sm:inline">Экспорт</span>
            </button>
            <div className="absolute right-0 top-9 z-20 hidden group-hover/export:block w-32 rounded-[8px] border border-[rgba(13,13,13,0.10)] bg-white shadow-lg overflow-hidden">
              <a
                href={exportChat(id, "md")}
                download
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-[12px] text-[rgba(13,13,13,0.70)] hover:bg-[rgba(13,13,13,0.04)]"
              >
                <FileText size={12} />
                Markdown
              </a>
              <a
                href={exportChat(id, "html")}
                download
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-[12px] text-[rgba(13,13,13,0.70)] hover:bg-[rgba(13,13,13,0.04)]"
              >
                <FileText size={12} />
                HTML
              </a>
            </div>
          </div>
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

      {/* Project instructions indicator */}
      {chat.project?.system_prompt && !instructionsDismissed && (
        <div
          className="flex shrink-0 items-center gap-2 px-4 py-2"
          style={{
            background: `${chat.project.color}0d`,
            borderBottom: `1px solid ${chat.project.color}22`,
          }}
        >
          <FileText size={13} style={{ color: chat.project.color, flexShrink: 0 }} />
          <span className="flex-1 truncate text-[12px]" style={{ color: chat.project.color }}>
            <span className="font-medium">{chat.project.name}</span>
            <span className="opacity-70"> · инструкции проекта активны</span>
          </span>
          <Link
            href={`/projects/${chat.project.id}/`}
            className="shrink-0 rounded-[5px] px-2 py-0.5 text-[11px] font-medium transition-colors hover:opacity-80"
            style={{ color: chat.project.color, background: `${chat.project.color}18` }}
          >
            Открыть
          </Link>
          <button
            onClick={() => setInstructionsDismissed(true)}
            className="shrink-0 rounded-[5px] p-0.5 transition-opacity hover:opacity-60"
            style={{ color: chat.project.color }}
          >
            <X size={12} />
          </button>
        </div>
      )}

      {/* Branch tree: parent link */}
      {chat?.parent_chat_id && (
        <div className="flex shrink-0 items-center gap-1.5 border-b border-[rgba(13,13,13,0.06)] px-4 py-1.5 text-[12px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.4)] dark:border-[rgba(255,255,255,0.06)]">
          <GitBranch size={11} className="shrink-0" />
          <span>Ветка от:</span>
          <a href={`/chat/${chat.parent_chat_id}/`} className="text-[#0a7cff] hover:underline">родительский чат</a>
        </div>
      )}

      {/* Branch tree: child branches */}
      {chat?.branches && chat.branches.length > 0 && (
        <div className="shrink-0 border-b border-[rgba(13,13,13,0.06)] px-4 py-2 dark:border-[rgba(255,255,255,0.06)]">
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.4)]">
            <GitBranch size={11} />
            Ветки ({chat.branches.length})
          </div>
          <div className="flex flex-wrap gap-1.5">
            {chat.branches.map((b) => (
              <a
                key={b.id}
                href={`/chat/${b.id}/`}
                className="rounded-[6px] border border-[rgba(13,13,13,0.1)] px-2 py-0.5 text-[11px] text-[rgba(13,13,13,0.6)] hover:border-[#0a7cff] hover:text-[#0a7cff] transition-colors dark:border-[rgba(255,255,255,0.1)] dark:text-[rgba(236,236,236,0.5)]"
              >
                {b.title || `Ветка #${b.id}`}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto" ref={scrollContainerRef} onScroll={handleScroll}>
        <div className="mx-auto max-w-4xl px-4 py-8">
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
                  onOpenArtifact={setActiveArtifact}
                  chatId={id}
                  isFalAi={chat.network.provider === "fal-ai"}
                  onEditImage={handleEditImage}
                  onAnimateImage={handleAnimateImage}
                  onUpscaleImage={handleUpscaleImage}
                  onVariationsImage={handleVariationsImage}
                  onStyleImage={handleStyleImage}
                  onVideoComplete={handleVideoComplete}
                  researchData={
                    msg.id === activeResearchMsgId && researchPoll
                      ? { steps: researchPoll.steps, status: researchPoll.status, error: researchPoll.error }
                      : undefined
                  }
                />
              ));
            })()}
          </div>

          <div ref={bottomRef} className="h-4" />
        </div>
        {showScrollBtn && (
          <div className="sticky bottom-4 flex justify-end pr-6 pb-1">
            <button
              onClick={scrollToBottom}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-[rgba(13,13,13,0.10)] bg-white shadow-md transition-all hover:shadow-lg active:scale-95"
              title="Прокрутить вниз"
            >
              <ChevronDown size={18} className="text-[rgba(13,13,13,0.55)]" />
            </button>
          </div>
        )}
      </div>

      {/* AI-proposed commit card (Sprint 4.3) */}
      {pendingCommit && (
        <div className="shrink-0 px-4 pb-1 pt-1" style={{ background: "var(--chat-page-bg)" }}>
          <div className="mx-auto max-w-2xl rounded-[12px] border border-[rgba(10,124,255,0.20)] bg-[rgba(10,124,255,0.05)] px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5 min-w-0">
                <GitCommit size={15} className="shrink-0 text-[#0a7cff]" />
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-[#0d0d0d]">
                    AI предложил коммит ({pendingCommit.files_count} {pendingCommit.files_count === 1 ? "файл" : pendingCommit.files_count < 5 ? "файла" : "файлов"})
                  </p>
                  <p className="truncate text-[11px] text-[rgba(13,13,13,0.50)]">{pendingCommit.commit_message}</p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button
                  disabled={commitActionLoading}
                  onClick={async () => {
                    setCommitActionLoading(true);
                    try {
                      await confirmCommit(pendingCommit.project_id, pendingCommit.id, "push");
                      setPendingCommit(null);
                    } finally {
                      setCommitActionLoading(false);
                    }
                  }}
                  className="flex items-center gap-1 rounded-[7px] bg-[#22a85a] px-2.5 py-1.5 text-[12px] font-medium text-white hover:bg-[#1a8a49] transition-colors disabled:opacity-50"
                >
                  <CheckCircle2 size={12} />
                  Подтвердить
                </button>
                <button
                  disabled={commitActionLoading}
                  onClick={async () => {
                    setCommitActionLoading(true);
                    try {
                      await confirmCommit(pendingCommit.project_id, pendingCommit.id, "reject");
                      setPendingCommit(null);
                    } finally {
                      setCommitActionLoading(false);
                    }
                  }}
                  className="flex items-center gap-1 rounded-[7px] border border-[rgba(13,13,13,0.15)] px-2.5 py-1.5 text-[12px] font-medium text-[rgba(13,13,13,0.60)] hover:border-[rgba(231,76,60,0.4)] hover:text-[#e74c3c] transition-colors disabled:opacity-50"
                >
                  <XCircle size={12} />
                  Отклонить
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

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
            {/* img2img: превью исходного изображения */}
            {sourceImage && (
              <div className="flex items-center gap-2.5 px-4 pt-3 pb-1">
                <div className="relative shrink-0">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={sourceImage.localUrl || sourceImage.url}
                    alt="Исходное изображение"
                    className="h-14 w-14 rounded-[10px] border object-cover"
                    style={{ borderColor: "var(--chat-input-border)" }}
                  />
                  {sourceImage.uploading && (
                    <div className="absolute inset-0 flex items-center justify-center rounded-[10px] bg-black/40">
                      <Loader2 size={16} className="animate-spin text-white" />
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={clearSourceImage}
                    className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-[rgba(13,13,13,0.10)] bg-white shadow-sm transition-colors hover:bg-[rgba(13,13,13,0.06)]"
                    title="Убрать исходное изображение"
                  >
                    <X size={11} className="text-[rgba(13,13,13,0.55)]" />
                  </button>
                </div>
                <div className="min-w-0">
                  <p className="flex items-center gap-1 text-[12px] font-medium text-[#0d0d0d] dark:text-[#ececec]">
                    <ImagePlus size={12} className="text-[#0a7cff]" />
                    Редактирование изображения
                  </p>
                  <p className="mt-0.5 text-[11px] text-[rgba(13,13,13,0.42)] dark:text-[rgba(236,236,236,0.4)]">
                    {sourceImage.uploading
                      ? "Загрузка..."
                      : sourceImage.error
                        ? "Ошибка загрузки"
                        : "Опишите изменения и отправьте"}
                  </p>
                </div>
              </div>
            )}
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
            <input
              ref={sourceInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => { if (e.target.files?.[0]) { handleSourceImage(e.target.files[0]); e.target.value = ""; } }}
            />
            {chat.network.provider === "fal-ai" ? (
              <button
                type="button"
                disabled={isBusy}
                onClick={() => sourceInputRef.current?.click()}
                title="Загрузить изображение для редактирования (img2img)"
                className="absolute bottom-2.5 right-[50px] flex h-9 w-9 items-center justify-center rounded-[10px] text-[rgba(13,13,13,0.4)] transition-all hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] disabled:cursor-not-allowed disabled:opacity-30 dark:text-[rgba(236,236,236,0.4)] dark:hover:bg-[rgba(255,255,255,0.08)] dark:hover:text-[#ececec]"
              >
                <ImagePlus size={16} />
              </button>
            ) : (
              <button
                type="button"
                disabled={isBusy}
                onClick={() => fileInputRef.current?.click()}
                className="absolute bottom-2.5 right-[50px] flex h-9 w-9 items-center justify-center rounded-[10px] text-[rgba(13,13,13,0.4)] transition-all hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] disabled:cursor-not-allowed disabled:opacity-30 dark:text-[rgba(236,236,236,0.4)] dark:hover:bg-[rgba(255,255,255,0.08)] dark:hover:text-[#ececec]"
              >
                <Paperclip size={16} />
              </button>
            )}
            <button
              type="submit"
              disabled={(text.trim() === "" && attachments.filter((a) => !a.error && !a.uploading).length === 0 && !sourceImage) || isBusy || sourceImage?.uploading === true}
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
                title={webSearch ? "Веб-поиск включён. Нажмите чтобы отключить" : "Включить поиск в интернете"}
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

              <button
                type="button"
                onClick={() => setVariantsMode((v) => !v)}
                title={variantsMode ? "Режим вариантов включён. Нажмите чтобы отключить" : "Получить 3 варианта ответа (Кратко / Подробно / Пошагово)"}
                className={[
                  "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-all",
                  variantsMode
                    ? "bg-[rgba(124,58,237,0.12)] text-[#7c3aed] ring-1 ring-[rgba(124,58,237,0.35)]"
                    : "text-[rgba(13,13,13,0.45)] hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.38)] dark:hover:text-[#ececec]",
                ].join(" ")}
              >
                <Layers size={12} />
                Варианты
                {variantsMode && (
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#7c3aed]" />
                )}
              </button>

              <button
                type="button"
                onClick={() => setResearchMode((v) => !v)}
                title={researchMode ? "Режим исследования включён. Нажмите чтобы отключить" : "Глубокое исследование — многошаговый автономный анализ с цитатами"}
                className={[
                  "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-all",
                  researchMode
                    ? "bg-[rgba(22,163,74,0.12)] text-[#16a34a] ring-1 ring-[rgba(22,163,74,0.35)]"
                    : "text-[rgba(13,13,13,0.45)] hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.38)] dark:hover:text-[#ececec]",
                ].join(" ")}
              >
                <Microscope size={12} />
                Исследование
                {researchMode && (
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#16a34a]" />
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

          {/* Тулбар для медиа-моделей (image/video): улучшение промпта + настройки */}
          {chat.network.provider === "fal-ai" && (
            <div className="mt-1.5 px-1">
              <div className="flex items-center gap-1">
                {/* AI-улучшение промпта — только для image-моделей */}
                {!chat.network.handle_video && chat.network.config_json?.metadata?.output_type !== "video" && (
                  <PromptEnhancer
                    prompt={text}
                    disabled={isBusy}
                    onAccept={(v) => {
                      setText(v);
                      requestAnimationFrame(autoResize);
                    }}
                  />
                )}
                {chat.network.config_json?.ui_settings ? (
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
                ) : null}
              </div>

              {showMediaSettings && chat.network.config_json?.ui_settings && (
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
                  <span className="font-medium text-[#0a7cff]">Ищем в интернете...</span>
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
    </div>{/* end main chat column */}

    {/* Artifact side panel */}
    {activeArtifact && (
      <div className="hidden h-full w-[45%] shrink-0 lg:flex lg:flex-col">
        <ArtifactPanel artifact={activeArtifact} onClose={() => setActiveArtifact(null)} />
      </div>
    )}

    {/* Sprint 4: Memory Toast */}
    {memoryToast && memoryToast.count > 0 && (
      <MemoryToast
        count={memoryToast.count}
        facts={memoryToast.facts}
        onDismiss={() => setMemoryToast(null)}
      />
    )}

    {/* Sprint 2: img2img edit modal (маска / outpaint) */}
    {editModalUrl && (
      <EditImageModal
        imageUrl={editModalUrl}
        chatId={id}
        onClose={() => setEditModalUrl(null)}
        onSubmit={handleEditModalSubmit}
      />
    )}

    {/* Sprint 3: img2video "Оживить" modal */}
    {animateModalUrl && (
      <AnimateImageModal
        imageUrl={animateModalUrl}
        onClose={() => setAnimateModalUrl(null)}
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
  onOpenArtifact,
  chatId,
  isFalAi,
  onEditImage,
  onAnimateImage,
  onUpscaleImage,
  onVariationsImage,
  onStyleImage,
  onVideoComplete,
  researchData,
}: {
  message: WebMessage;
  networkAvatar: string | null;
  networkName: string;
  shouldAnimate: boolean;
  streamingText?: string;
  canRegenerate?: boolean;
  onRegenerate?: () => void;
  onOpenArtifact?: (a: Artifact) => void;
  chatId?: number;
  isFalAi?: boolean;
  onEditImage?: (url: string) => void;
  onAnimateImage?: (url: string) => void;
  onUpscaleImage?: (generationId: number, factor: 2 | 4) => void;
  onVariationsImage?: (generationId: number) => void;
  onStyleImage?: (url: string) => void;
  onVideoComplete?: () => void;
  researchData?: { steps: import("@/lib/api/types").DeepResearchStep[]; status: import("@/lib/api/types").DeepResearchStatus; error: string };
}) {
  const isUser = message.role === "user";
  const [savedFact, setSavedFact] = useState(false);
  const [branchLoading, setBranchLoading] = useState(false);
  const [forgetPanelMsgId, setForgetPanelMsgId] = useState<number | null>(null);

  if (isUser) {
    return (
      <div className="group flex flex-col items-end gap-1">
        <div
          className="max-w-[78%] rounded-[18px] rounded-br-[4px] px-4 py-3 text-[14px] leading-relaxed text-white"
          style={{ background: "var(--chat-user-bubble)" }}
        >
          <PlainText text={message.content} />
        </div>
        {/* User message quick actions */}
        {message.content && (
          <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              onClick={async () => {
                if (savedFact) return;
                try {
                  await quickSaveFact(message.content);
                  setSavedFact(true);
                  setTimeout(() => setSavedFact(false), 2000);
                } catch {}
              }}
              className="flex h-6 items-center gap-1 rounded-[5px] px-2 text-[11px] font-medium text-[rgba(13,13,13,0.42)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.38)]"
              title="Запомнить это сообщение как факт памяти"
            >
              <BookmarkPlus size={11} />
              {savedFact ? "Запомнено" : "Запомнить"}
            </button>
            {chatId && (
              <button
                onClick={async () => {
                  if (branchLoading) return;
                  setBranchLoading(true);
                  try {
                    const result = await branchChat(chatId, message.id);
                    window.location.href = `/chat/${result.chat_id}/`;
                  } catch {
                    setBranchLoading(false);
                  }
                }}
                className="flex h-6 items-center gap-1 rounded-[5px] px-2 text-[11px] font-medium text-[rgba(13,13,13,0.42)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.38)]"
                title="Создать ветку разговора от этого сообщения"
              >
                {branchLoading ? <Loader size={11} className="animate-spin" /> : <GitBranch size={11} />}
                Ветка
              </button>
            )}
          </div>
        )}
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
        ) : researchData && (researchData.status === "pending" || researchData.status === "running") ? (
          <DeepResearchPanel steps={researchData.steps} status={researchData.status} error={researchData.error} />
        ) : researchData?.status === "error" ? (
          <>
            <DeepResearchPanel steps={researchData.steps} status={researchData.status} error={researchData.error} />
            <p className="mt-2 text-[13px] text-red-500">Ошибка исследования. Попробуйте ещё раз.</p>
          </>
        ) : message.status === "pending" ? (
          isFalAi && message.generation_id ? (
            <div className="py-1">
              <GenerationProgress
                generationId={message.generation_id}
                onComplete={onVideoComplete}
              />
            </div>
          ) : (
            <div className="flex items-center gap-1 py-2">
              <BouncingDots />
            </div>
          )
        ) : message.status === "failed" ? (
          <p className="text-[14px] text-[#e74c3c]">
            {message.error_message ?? "Ошибка генерации. Попробуйте ещё раз."}
          </p>
        ) : (
          <>
            {message.search_context && (
              <SearchContextBlock context={message.search_context} />
            )}
            {message.is_research && message.content ? (
              <ResearchReport html={message.content} plainText={message.plain_text ?? undefined} />
            ) : (
              <AssistantContent
                content={message.content}
                plain_text={message.plain_text ?? null}
                shouldAnimate={shouldAnimate}
                sources={message.kb_sources}
              />
            )}
            {message.kb_sources && message.kb_sources.length > 0 && (
              <SourcesBlock sources={message.kb_sources} />
            )}
            {message.variants && message.variants.length >= 1 && (
              <ResponseVariants variants={message.variants} />
            )}
            {/* Image action bar — всегда видима для fal-ai сообщений с изображением */}
            {isFalAi && (() => {
              const imgUrl = extractFirstImageUrl(message.content || message.plain_text || "");
              if (!imgUrl && !message.image_generation_id) return null;
              const btnCls = "flex h-7 items-center gap-1.5 rounded-[6px] px-2 text-[12px] font-medium transition-all";
              const btnStyle = { color: "rgba(10,124,255,0.9)" };
              const onEnter = (e: React.MouseEvent<HTMLButtonElement>) => {
                e.currentTarget.style.background = "rgba(10,124,255,0.08)";
                e.currentTarget.style.color = "#0a7cff";
              };
              const onLeave = (e: React.MouseEvent<HTMLButtonElement>) => {
                e.currentTarget.style.background = "";
                e.currentTarget.style.color = "rgba(10,124,255,0.9)";
              };
              return (
                <div className="mt-2 flex flex-wrap items-center gap-1 border-t border-[rgba(13,13,13,0.07)] pt-2 dark:border-[rgba(236,236,236,0.07)]">
                  {imgUrl && onEditImage && (
                    <button onClick={() => onEditImage(imgUrl)} className={btnCls} style={btnStyle} onMouseEnter={onEnter} onMouseLeave={onLeave} title="Редактировать изображение (img2img)">
                      <Pencil size={13} /><span>Редактировать</span>
                    </button>
                  )}
                  {imgUrl && onAnimateImage && (
                    <button onClick={() => onAnimateImage(imgUrl)} className={btnCls} style={btnStyle} onMouseEnter={onEnter} onMouseLeave={onLeave} title="Оживить изображение в видео">
                      <Film size={13} /><span>Оживить</span>
                    </button>
                  )}
                  {message.image_generation_id && onUpscaleImage && (
                    <>
                      <button onClick={() => onUpscaleImage(message.image_generation_id!, 2)} className={btnCls} style={btnStyle} onMouseEnter={onEnter} onMouseLeave={onLeave} title="Улучшить детализацию и чёткость (2×)">
                        <Maximize2 size={13} /><span>Улучшить 2×</span>
                      </button>
                      <button onClick={() => onUpscaleImage(message.image_generation_id!, 4)} className={btnCls} style={btnStyle} onMouseEnter={onEnter} onMouseLeave={onLeave} title="Улучшить детализацию и чёткость (4×)">
                        <Maximize2 size={13} /><span>Улучшить 4×</span>
                      </button>
                    </>
                  )}
                  {message.image_generation_id && onVariationsImage && (
                    <button onClick={() => onVariationsImage(message.image_generation_id!)} className={btnCls} style={btnStyle} onMouseEnter={onEnter} onMouseLeave={onLeave} title="Создать 4 вариации">
                      <Images size={13} /><span>Варианты</span>
                    </button>
                  )}
                  {imgUrl && onStyleImage && (
                    <button onClick={() => onStyleImage(imgUrl)} className={btnCls} style={btnStyle} onMouseEnter={onEnter} onMouseLeave={onLeave} title="Использовать как референс стиля">
                      <Palette size={13} /><span>Стиль</span>
                    </button>
                  )}
                </div>
              );
            })()}

            {/* Hover action bar — копирование, повтор, озвучка */}
            <div className="mt-1.5 flex items-center gap-0.5 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
              <CopyButton plainText={message.plain_text} htmlContent={message.content} />
              {(() => {
                const artifact = onOpenArtifact ? extractArtifact(message.plain_text || message.content) : null;
                return artifact && onOpenArtifact ? (
                  <button
                    onClick={() => onOpenArtifact(artifact)}
                    className="flex h-7 items-center gap-1.5 rounded-[6px] px-2 text-[12px] font-medium transition-colors"
                    style={{ color: "rgba(10,124,255,0.8)" }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.background = "rgba(10,124,255,0.08)";
                      (e.currentTarget as HTMLButtonElement).style.color = "#0a7cff";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.background = "";
                      (e.currentTarget as HTMLButtonElement).style.color = "rgba(10,124,255,0.8)";
                    }}
                    title="Открыть превью артефакта"
                  >
                    <Layers size={13} />
                    <span>Preview</span>
                  </button>
                ) : null;
              })()}
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
            {/* Brain indicator + Забыть — только для assistant с used_memory */}
            {message.used_memory && (
              <div className="relative mt-1 flex items-center gap-1">
                <div className="relative">
                  <button
                    onClick={() => setForgetPanelMsgId((v) => v === message.id ? null : message.id)}
                    className="flex items-center gap-1 rounded-[6px] px-1.5 py-1 text-[11px] text-[rgba(124,58,237,0.6)] hover:bg-[rgba(124,58,237,0.07)] hover:text-[#7c3aed] transition-colors"
                    title="Забыть из памяти"
                  >
                    <Brain size={12} />
                    <span className="text-[10px]">Память</span>
                  </button>
                  {forgetPanelMsgId === message.id && (
                    <ForgetMemoryPanel onClose={() => setForgetPanelMsgId(null)} />
                  )}
                </div>
              </div>
            )}
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
  const queueRef = useRef("");
  const enqueuedRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (text.length > enqueuedRef.current) {
      queueRef.current += text.slice(enqueuedRef.current);
      enqueuedRef.current = text.length;
    }
  }, [text]);

  useEffect(() => {
    function drain() {
      const q = queueRef.current;
      if (q.length > 0) {
        let end = Math.min(12, q.length);
        // Drain only up to last word boundary so whole words appear at once
        if (end < q.length) {
          for (let i = end - 1; i > 0; i--) {
            if (q[i] === " " || q[i] === "\n") { end = i + 1; break; }
          }
        }
        // Capture chunk BEFORE mutating queue — fixes the race condition
        const chunk = q.slice(0, end);
        queueRef.current = q.slice(end);
        setDisplayed((prev) => prev + chunk);
      }
      rafRef.current = requestAnimationFrame(drain);
    }
    rafRef.current = requestAnimationFrame(drain);
    return () => { if (rafRef.current !== null) cancelAnimationFrame(rafRef.current); };
  }, []);

  return (
    <div
      className="text-[15px] leading-[1.75]"
      style={{ color: "rgba(13,13,13,0.86)" }}
    >
      <PlainText text={displayed || " "} />
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
  sources,
}: {
  content: string;
  plain_text: string | null;
  shouldAnimate: boolean;
  sources?: KBSource[];
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

  // Attach cite-ref tooltips (KB inline citations).
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !sources?.length) return;
    const spans = container.querySelectorAll<HTMLElement>(".cite-ref");
    spans.forEach((span) => {
      const n = parseInt(span.dataset.cite ?? "0", 10);
      const src = sources[n - 1];
      if (!src) return;
      span.style.cursor = "pointer";
      span.style.color = "#0a7cff";
      span.title = `${src.filename}${src.snippet ? ": " + src.snippet : ""}`;
    });
  }, [content, sources]);

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
          Результаты поиска
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

/* ─── KB Sources block ───────────────────────────────────── */
function SourcesBlock({ sources }: { sources: KBSource[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2.5 rounded-[10px] border border-[rgba(10,124,255,0.14)] bg-[rgba(10,124,255,0.03)]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        <FileText size={13} className="shrink-0 text-[#0a7cff]" />
        <span className="flex-1 text-[12px] font-medium text-[#0a7cff]">
          Источники ({sources.length})
        </span>
        {open ? (
          <ChevronDown size={13} className="shrink-0 text-[rgba(10,124,255,0.6)]" />
        ) : (
          <ChevronRight size={13} className="shrink-0 text-[rgba(10,124,255,0.6)]" />
        )}
      </button>
      {open && (
        <div className="border-t border-[rgba(10,124,255,0.1)] px-3 pb-2 pt-1.5 flex flex-col gap-1">
          {sources.map((s) => (
            <div
              key={s.id}
              className="group/src relative flex flex-col gap-0.5 rounded-[6px] px-2 py-1.5 text-[12px] text-[rgba(13,13,13,0.7)] dark:text-[rgba(236,236,236,0.6)] hover:bg-[rgba(10,124,255,0.06)] transition-colors"
            >
              <div className="flex items-center gap-2">
                <FileText size={11} className="shrink-0 text-[rgba(10,124,255,0.5)]" />
                <span className="font-mono truncate" title={s.path}>{s.filename}</span>
                {s.path !== s.filename && (
                  <span className="ml-auto shrink-0 text-[10px] text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.3)] font-mono truncate max-w-[180px]" title={s.path}>
                    {s.path}
                  </span>
                )}
              </div>
              {s.snippet && (
                <div className="hidden group-hover/src:block ml-5 text-[11px] leading-relaxed text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.38)] line-clamp-2">
                  {s.snippet}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
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
