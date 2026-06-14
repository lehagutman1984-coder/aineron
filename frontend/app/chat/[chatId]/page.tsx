"use client";

import { useState, useRef, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PenSquare, Send, Code2, LayoutGrid } from "lucide-react";
import {
  getChat,
  sendMessage,
  getMessageStatus,
} from "@/lib/api/client";
import { APIError } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";
import type { WebMessage, ChatDetail } from "@/lib/api/types";

const POLL_INTERVAL = 1500;

export default function ChatPage() {
  const { chatId } = useParams<{ chatId: string }>();
  const id = Number(chatId);
  const router = useRouter();
  const qc = useQueryClient();
  const { user, setStars } = useAuthStore();

  const [text, setText] = useState("");
  const [pendingMessageId, setPendingMessageId] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Fetch chat detail
  const { data: chat, isLoading, error } = useQuery<ChatDetail>({
    queryKey: ["chat", id],
    queryFn: () => getChat(id),
    staleTime: 0,
    retry: 1,
  });

  // Poll for pending message status
  const { data: polledMessage } = useQuery<WebMessage>({
    queryKey: ["message-status", pendingMessageId],
    queryFn: () => getMessageStatus(pendingMessageId!),
    enabled: pendingMessageId !== null,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return POLL_INTERVAL;
      if (data.status === "pending") return POLL_INTERVAL;
      return false;
    },
  });

  // When polling resolves, merge into chat cache
  useEffect(() => {
    if (!polledMessage) return;
    if (polledMessage.status === "pending") return;

    // Stop polling
    setPendingMessageId(null);

    // Merge the completed assistant message into the chat cache
    qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        messages: prev.messages.map((m) =>
          m.id === polledMessage.id ? polledMessage : m
        ),
      };
    });

    if (polledMessage.status === "completed") {
      // Update balance if possible — refetch user
    }
  }, [polledMessage, id, qc]);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat?.messages, polledMessage]);

  const sendMutation = useMutation({
    mutationFn: (msg: string) => sendMessage(id, { message: msg }),
    onMutate: async (msg) => {
      // Optimistically add user message
      const optimisticUser: WebMessage = {
        id: Date.now(),
        role: "user",
        content: msg,
        files: [],
        status: "completed",
        error_message: null,
        created_at: new Date().toISOString(),
      };
      const optimisticAssistant: WebMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: "",
        files: [],
        status: "pending",
        error_message: null,
        created_at: new Date().toISOString(),
      };
      qc.setQueryData<ChatDetail>(["chat", id], (prev) =>
        prev
          ? { ...prev, messages: [...prev.messages, optimisticUser, optimisticAssistant] }
          : prev
      );
      setText("");
    },
    onSuccess: (res) => {
      setStars(res.new_balance);
      setPendingMessageId(res.assistant_message_id);
      // Replace optimistic assistant with real one (id updated)
      qc.setQueryData<ChatDetail>(["chat", id], (prev) => {
        if (!prev) return prev;
        const msgs = prev.messages.slice(0, -1);
        return {
          ...prev,
          messages: [
            ...msgs,
            {
              id: res.assistant_message_id,
              role: "assistant" as const,
              content: "",
              files: [],
              status: "pending" as const,
              error_message: null,
              created_at: new Date().toISOString(),
            },
          ],
        };
      });
    },
    onError: (err) => {
      // Remove optimistic messages on error
      qc.invalidateQueries({ queryKey: ["chat", id] });
      setText(text); // restore input
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const msg = text.trim();
    if (!msg || sendMutation.isPending || pendingMessageId !== null) return;
    sendMutation.mutate(msg);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[calc(100vh-56px)] items-center justify-center text-[14px] text-[rgba(13,13,13,0.45)]">
        Загрузка...
      </div>
    );
  }

  if (error || !chat) {
    return (
      <div className="flex h-[calc(100vh-56px)] flex-col items-center justify-center gap-4 text-center">
        <p className="text-[15px] text-[rgba(13,13,13,0.6)]">Чат не найден</p>
        <Link href="/account/" className="text-[14px] text-[#0a7cff] hover:underline">
          Вернуться в кабинет
        </Link>
      </div>
    );
  }

  const isPending = pendingMessageId !== null;

  return (
    <div className="flex h-[calc(100vh-56px)] flex-col">
      {/* Header */}
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-[rgba(13,13,13,0.10)] bg-white px-4">
        {/* Model name */}
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {chat.network.avatar ? (
            <img
              src={chat.network.avatar}
              alt={chat.network.name}
              width={22}
              height={22}
              className="rounded-[5px]"
            />
          ) : (
            <div className="flex h-[22px] w-[22px] flex-shrink-0 items-center justify-center rounded-[5px] bg-[rgba(10,124,255,0.12)] text-[#0a7cff]">
              <Code2 size={13} />
            </div>
          )}
          <span className="truncate text-[14px] font-medium text-[#0d0d0d]">
            {chat.network.name}
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <Link
            href="/models/"
            className="flex h-8 items-center gap-1.5 rounded-[7px] px-3 text-[12px] font-medium text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] transition-colors"
            title="Выбрать другую модель"
          >
            <LayoutGrid size={14} />
            <span className="hidden sm:inline">Модели</span>
          </Link>
          <Link
            href="/models/"
            className="flex h-8 items-center gap-1.5 rounded-[7px] bg-[#0a7cff] px-3 text-[12px] font-medium text-white hover:bg-[#0066cc] transition-colors"
            title="Начать новый чат"
          >
            <PenSquare size={14} />
            <span className="hidden sm:inline">Новый чат</span>
          </Link>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {chat.messages.length === 0 && (
            <div className="py-12 text-center text-[14px] text-[rgba(13,13,13,0.4)]">
              Начните диалог
            </div>
          )}
          {chat.messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-[rgba(13,13,13,0.10)] bg-white px-4 py-3">
        <form onSubmit={handleSubmit} className="mx-auto max-w-3xl">
          {sendMutation.error instanceof APIError && (
            <div className="mb-2 text-[13px] text-[#e74c3c]">
              {(sendMutation.error as APIError).message}
            </div>
          )}
          <div className="relative flex items-end gap-2">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Введите сообщение..."
              rows={1}
              disabled={isPending}
              className="flex-1 resize-none rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-4 py-3 pr-2 text-[14px] text-[#0d0d0d] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] disabled:opacity-50 transition-all"
              style={{ maxHeight: "200px" }}
              onInput={(e) => {
                const t = e.currentTarget;
                t.style.height = "auto";
                t.style.height = Math.min(t.scrollHeight, 200) + "px";
              }}
            />
            <button
              type="submit"
              disabled={!text.trim() || isPending || sendMutation.isPending}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] bg-[#0a7cff] text-white hover:bg-[#0066cc] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              <Send size={16} />
            </button>
          </div>
          {isPending && (
            <p className="mt-1.5 text-[12px] text-[rgba(13,13,13,0.45)]">
              Нейросеть печатает...
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: WebMessage }) {
  const isUser = message.role === "user";
  const isPending = message.status === "pending";
  const isFailed = message.status === "failed";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={[
          "max-w-[80%] rounded-[12px] px-4 py-3 text-[14px] leading-relaxed",
          isUser
            ? "bg-[#0a7cff] text-white"
            : "border border-[rgba(13,13,13,0.10)] bg-white text-[#0d0d0d]",
        ].join(" ")}
      >
        {isPending ? (
          <span className="inline-flex items-center gap-1 text-[rgba(13,13,13,0.4)]">
            <span className="animate-pulse">...</span>
          </span>
        ) : isFailed ? (
          <span className="text-[#e74c3c]">
            {message.error_message ?? "Ошибка генерации"}
          </span>
        ) : (
          <MessageContent content={message.content} />
        )}
      </div>
    </div>
  );
}

function MessageContent({ content }: { content: string }) {
  // Check if content contains HTML (from code formatter)
  if (content.includes("<pre") || content.includes("<code") || content.includes("<p>")) {
    return (
      <div
        className="prose prose-sm max-w-none"
        dangerouslySetInnerHTML={{ __html: content }}
      />
    );
  }
  // Plain text with line breaks
  return (
    <>
      {content.split("\n").map((line, i) => (
        <span key={i}>
          {line}
          {i < content.split("\n").length - 1 && <br />}
        </span>
      ))}
    </>
  );
}
