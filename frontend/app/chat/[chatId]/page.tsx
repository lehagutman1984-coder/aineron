"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Send, LayoutGrid, PenSquare, Code2 } from "lucide-react";
import { getChat, sendMessage, getMessageStatus, streamMessage, APIError } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";
import type { WebMessage, ChatDetail } from "@/lib/api/types";

const POLL_INTERVAL = 800;

const detectHTML = (s: string) =>
  /<(pre|code|div|p|ul|ol|h[1-6]|blockquote|table|img|br)\b/i.test(s);

export default function ChatPage() {
  const { chatId } = useParams<{ chatId: string }>();
  const id = Number(chatId);
  const qc = useQueryClient();
  const { setStars } = useAuthStore();

  const [text, setText] = useState("");

  // Polling state (used for fal-ai image models)
  const [pendingMessageId, setPendingMessageId] = useState<number | null>(null);

  // SSE streaming state (used for text models)
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [streamingAssistId, setStreamingAssistId] = useState<number | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

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

  // Mutation for fal-ai image models (uses polling)
  const sendMutation = useMutation({
    mutationFn: (msg: string) => sendMessage(id, { message: msg }),
    onMutate: async (msg) => {
      const now = Date.now();
      qc.setQueryData<ChatDetail>(["chat", id], (prev) =>
        prev
          ? {
              ...prev,
              messages: [
                ...prev.messages,
                { id: now, role: "user", content: msg, files: [], status: "completed", error_message: null, created_at: new Date().toISOString() },
                { id: now + 1, role: "assistant", content: "", files: [], status: "pending", error_message: null, created_at: new Date().toISOString() },
              ],
            }
          : prev
      );
      setText("");
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
            { id: res.assistant_message_id, role: "assistant" as const, content: "", files: [], status: "pending" as const, error_message: null, created_at: new Date().toISOString() },
          ],
        };
      });
    },
    onError: () => {
      qc.invalidateQueries({ queryKey: ["chat", id] });
    },
  });

  // Handler for text models — real SSE streaming
  const handleStreamSubmit = useCallback(
    async (msg: string) => {
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
                { id: tempUserId, role: "user", content: msg, files: [], status: "completed", error_message: null, created_at: new Date().toISOString() },
                { id: tempAssistId, role: "assistant", content: "", files: [], status: "pending", error_message: null, created_at: new Date().toISOString() },
              ],
            }
          : prev
      );
      setText("");
      if (textareaRef.current) textareaRef.current.style.height = "auto";

      let realAssistId = tempAssistId;

      try {
        await streamMessage(id, { message: msg }, {
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
          onToken: (token) => {
            setStreamText((prev) => prev + token);
          },
          onDone: ({ content }) => {
            qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
              if (!prev) return prev;
              return {
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === realAssistId
                    ? { ...m, content, status: "completed" as const }
                    : m
                ),
              };
            });
            setIsStreaming(false);
            setStreamText("");
            setStreamingAssistId(null);
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
    [id, qc, setStars]
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const msg = text.trim();
    if (!msg || isBusy) return;
    if (chat?.network.provider === "fal-ai") {
      sendMutation.mutate(msg);
    } else {
      handleStreamSubmit(msg);
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

  const isPending = pendingMessageId !== null;
  const isBusy = isPending || sendMutation.isPending || isStreaming;

  const displayError =
    streamError ??
    (sendMutation.error instanceof APIError ? (sendMutation.error as APIError).message : null);

  return (
    <div className="flex h-full flex-col" style={{ background: "#f7f7f5" }}>
      {/* Header */}
      <header
        className="flex h-12 shrink-0 items-center justify-between px-4"
        style={{
          background: "white",
          borderBottom: "1px solid rgba(13,13,13,0.08)",
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
            <div className="flex flex-col items-center py-20 text-center">
              {chat.network.avatar ? (
                <img
                  src={chat.network.avatar}
                  alt=""
                  width={60}
                  height={60}
                  className="mb-5 rounded-[16px]"
                  style={{ boxShadow: "0 4px 16px rgba(0,0,0,0.10)" }}
                />
              ) : (
                <div
                  className="mb-5 flex h-[60px] w-[60px] items-center justify-center rounded-[16px] text-[#0a7cff]"
                  style={{ background: "rgba(10,124,255,0.10)" }}
                >
                  <Code2 size={28} />
                </div>
              )}
              <p className="text-[18px] font-semibold text-[#0d0d0d]">
                {chat.network.name}
              </p>
              <p className="mt-1.5 text-[14px] text-[rgba(13,13,13,0.42)]">
                Введите вопрос или задачу ниже
              </p>
            </div>
          )}

          <div className="flex flex-col gap-7">
            {chat.messages.map((msg) => (
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
              />
            ))}
          </div>

          <div ref={bottomRef} className="h-4" />
        </div>
      </div>

      {/* Input */}
      <div className="shrink-0 px-4 pb-5 pt-2" style={{ background: "#f7f7f5" }}>
        {displayError && (
          <p className="mx-auto mb-2 max-w-2xl text-[13px] text-[#e74c3c]">
            {displayError}
          </p>
        )}

        <form onSubmit={handleSubmit} className="mx-auto max-w-2xl">
          <div
            className="relative overflow-hidden rounded-[14px] transition-all"
            style={{
              background: "white",
              border: "1px solid rgba(13,13,13,0.12)",
              boxShadow: "0 2px 12px rgba(0,0,0,0.07)",
            }}
          >
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
              className="block w-full resize-none bg-transparent px-4 py-3.5 pr-14 text-[14px] leading-relaxed text-[#0d0d0d] outline-none disabled:opacity-50"
              style={{ maxHeight: "200px", caretColor: "#0a7cff" }}
            />
            <button
              type="submit"
              disabled={!text.trim() || isBusy}
              className="absolute bottom-2.5 right-2.5 flex h-9 w-9 items-center justify-center rounded-[10px] text-white transition-all disabled:cursor-not-allowed disabled:opacity-25"
              style={{ background: "#0d0d0d" }}
            >
              <Send size={15} />
            </button>
          </div>

          {isBusy && (
            <div className="mt-2 flex items-center gap-2 px-1">
              <BouncingDots />
              <span className="text-[12px] text-[rgba(13,13,13,0.42)]">
                {chat.network.name} отвечает...
              </span>
            </div>
          )}
        </form>
      </div>
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
}: {
  message: WebMessage;
  networkAvatar: string | null;
  networkName: string;
  shouldAnimate: boolean;
  streamingText?: string;
}) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[78%] rounded-[18px] rounded-br-[4px] px-4 py-3 text-[14px] leading-relaxed text-white"
          style={{ background: "#0d0d0d" }}
        >
          <PlainText text={message.content} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
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
          <AssistantContent content={message.content} shouldAnimate={shouldAnimate} />
        )}
      </div>
    </div>
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

/* ─── Live streaming display (tokens arriving in real time) ─ */
function StreamingDisplay({ text }: { text: string }) {
  return (
    <div
      className="text-[15px] leading-[1.75]"
      style={{ color: "rgba(13,13,13,0.86)" }}
    >
      <PlainText text={text || " "} />
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
  shouldAnimate,
}: {
  content: string;
  shouldAnimate: boolean;
}) {
  const html = detectHTML(content);
  const containerRef = useRef<HTMLDivElement>(null);

  // Lock animation decision on mount — only animate plain text, not HTML
  const doAnimate = useRef(shouldAnimate && !html && content.length > 0);
  const [displayed, setDisplayed] = useState(doAnimate.current ? "" : content);
  const [showCursor, setShowCursor] = useState(doAnimate.current);

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
  }, []); // runs once on mount

  // Attach copy handlers to Django CodeFormatter buttons
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

  if (html) {
    return (
      <div
        ref={containerRef}
        className="chat-prose"
        dangerouslySetInnerHTML={{ __html: content }}
      />
    );
  }

  return (
    <div
      className="text-[15px] leading-[1.75]"
      style={{ color: "rgba(13,13,13,0.86)" }}
    >
      <PlainText text={displayed} />
      {showCursor && (
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
      )}
    </div>
  );
}
