"use client";

/**
 * S6 — Mini App 2.0: из лаунчера в приложение.
 * Экраны: Главная (баланс, действия) / Галерея (генерации, шаринг) / Чат.
 * Fullscreen, addToHomeScreen, shareMessage, shareToStory, SecureStorage.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Wallet,
  Images,
  MessageSquare,
  Download,
  Share2,
  CircleUser,
  Send,
  Sparkles,
  SmartphoneNfc,
} from "lucide-react";
import { formatMoney } from "@/lib/money";
import {
  initMiniApp,
  promptAddToHomeScreen,
  shareMessage,
  shareToStory,
  downloadFile,
  haptic,
  secureSet,
  secureGet,
  getTg,
} from "@/lib/telegram-webapp";

const BOT_USERNAME = "aineron_bot";

interface UserInfo {
  id: number;
  email: string;
  balance_kopecks: number;
}

interface GalleryFile {
  id: number;
  url: string;
  prompt: string;
  media_type: string;
}

type Tab = "home" | "gallery" | "chat";

async function api<T>(
  path: string,
  token: string,
  init: RequestInit = {}
): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers as Record<string, string>),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { error?: { message?: string } })?.error?.message ??
        `HTTP ${res.status}`
    );
  }
  return res.json() as Promise<T>;
}

export default function TelegramMiniApp() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [token, setToken] = useState<string>("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("home");

  useEffect(() => {
    initMiniApp();
    const tg = getTg();
    const initData = tg?.initData || "";
    if (!initData) {
      setError("Откройте через Telegram-бот (@aineron_bot)");
      setLoading(false);
      return;
    }
    fetch("/api/v1/telegram/webapp-auth/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: initData }),
    })
      .then((r) => r.json())
      .then(async (data) => {
        if (data.access) {
          // S6: JWT в SecureStorage вместо localStorage
          secureSet("tg_access_token", data.access);
          if (data.refresh) secureSet("tg_refresh_token", data.refresh);
          setToken(data.access);
          setUser(data.user);
        } else {
          const cached = await secureGet("tg_access_token");
          if (cached) setToken(cached);
          setError(data.error || "Ошибка авторизации");
        }
        setLoading(false);
      })
      .catch(() => {
        setError("Ошибка сети");
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <div style={{ padding: 40, textAlign: "center", fontFamily: "system-ui" }}>Загрузка...</div>;
  }
  if (error && !user) {
    return (
      <div style={{ padding: 24, fontFamily: "system-ui" }}>
        <p style={{ color: "var(--tg-theme-destructive-text-color, #e74c3c)" }}>
          {error}
        </p>
        <p style={{ fontSize: 14, color: "var(--tg-theme-hint-color, #666)" }}>
          Привяжите аккаунт: напишите /start боту и следуйте инструкциям.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        fontFamily: "system-ui",
        background: "var(--tg-theme-bg-color, #fff)",
        color: "var(--tg-theme-text-color, #000)",
        minHeight: "100vh",
        paddingBottom: 72,
      }}
    >
      <div style={{ maxWidth: 520, margin: "0 auto", padding: 16 }}>
        {tab === "home" && user && (
          <HomeScreen user={user} onOpenGallery={() => setTab("gallery")} />
        )}
        {tab === "gallery" && token && <GalleryScreen token={token} />}
        {tab === "chat" && token && <ChatScreen token={token} />}
      </div>

      {/* Нижняя навигация */}
      <nav
        style={{
          position: "fixed",
          bottom: 0,
          left: 0,
          right: 0,
          display: "flex",
          borderTop: "1px solid var(--tg-theme-section-separator-color, #e5e5e5)",
          background: "var(--tg-theme-bg-color, #fff)",
          zIndex: 10,
        }}
      >
        {(
          [
            { key: "home", label: "Баланс", Icon: Wallet },
            { key: "gallery", label: "Галерея", Icon: Images },
            { key: "chat", label: "Чат", Icon: MessageSquare },
          ] as { key: Tab; label: string; Icon: typeof Wallet }[]
        ).map(({ key, label, Icon }) => (
          <button
            key={key}
            onClick={() => {
              haptic("light");
              setTab(key);
            }}
            style={{
              flex: 1,
              padding: "10px 0 12px",
              border: "none",
              background: "transparent",
              color:
                tab === key
                  ? "var(--tg-theme-accent-text-color, #C4623E)"
                  : "var(--tg-theme-hint-color, #888)",
              fontSize: 12,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 3,
              cursor: "pointer",
            }}
          >
            <Icon size={20} />
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}

// ─── Главная ───

function HomeScreen({
  user,
  onOpenGallery,
}: {
  user: UserInfo;
  onOpenGallery: () => void;
}) {
  const linkStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "13px 16px",
    background: "var(--tg-theme-secondary-bg-color, #f5f5f5)",
    color: "var(--tg-theme-text-color, #000)",
    borderRadius: 12,
    textDecoration: "none",
    fontWeight: 500,
    fontSize: 15,
    border: "none",
    width: "100%",
    cursor: "pointer",
    textAlign: "left" as const,
  };

  return (
    <>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 12 }}>aineron</h2>
      <div
        style={{
          background: "var(--tg-theme-secondary-bg-color, #f5f5f5)",
          borderRadius: 14,
          padding: 18,
          marginBottom: 16,
        }}
      >
        <div
          style={{
            fontSize: 13,
            color: "var(--tg-theme-hint-color, #666)",
            marginBottom: 4,
          }}
        >
          Баланс
        </div>
        <div style={{ fontSize: 34, fontWeight: 700 }}>
          {formatMoney(user.balance_kopecks)}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <a href="/account/billing/" style={linkStyle}>
          <Wallet size={18} /> Пополнить баланс
        </a>
        <button onClick={onOpenGallery} style={linkStyle}>
          <Images size={18} /> Мои генерации
        </button>
        <a href="/account/tasks/" style={linkStyle}>
          <Sparkles size={18} /> AI-задачи по расписанию
        </a>
        <a href="/account/analytics/" style={linkStyle}>
          <CircleUser size={18} /> Аналитика трат
        </a>
        <button
          onClick={() => {
            haptic("medium");
            promptAddToHomeScreen();
          }}
          style={linkStyle}
        >
          <SmartphoneNfc size={18} /> Добавить на главный экран
        </button>
      </div>

      <p
        style={{
          marginTop: 18,
          fontSize: 12,
          color: "var(--tg-theme-hint-color, #999)",
          textAlign: "center",
        }}
      >
        {user.email}
      </p>
    </>
  );
}

// ─── Галерея ───

function GalleryScreen({ token }: { token: string }) {
  const [files, setFiles] = useState<GalleryFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    api<{ files: GalleryFile[] }>("/telegram/webapp/files/", token)
      .then((d) => setFiles(d.files))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  const handleShare = useCallback(
    async (f: GalleryFile) => {
      haptic("medium");
      setBusyId(f.id);
      try {
        const res = await api<{
          prepared_message_id: string | null;
          fallback_url?: string;
        }>("/telegram/webapp/prepare-share/", token, {
          method: "POST",
          body: JSON.stringify({ generation_id: f.id }),
        });
        if (res.prepared_message_id) {
          const ok = shareMessage(res.prepared_message_id, () =>
            haptic("success")
          );
          if (ok) return;
        }
        const url =
          res.fallback_url ??
          `https://t.me/share/url?url=${encodeURIComponent(f.url)}`;
        window.open(url, "_blank");
      } catch {
        window.open(
          `https://t.me/share/url?url=${encodeURIComponent(f.url)}`,
          "_blank"
        );
      } finally {
        setBusyId(null);
      }
    },
    [token]
  );

  if (loading) return <div style={{ padding: 40, textAlign: "center" }}>Загрузка галереи...</div>;
  if (!files.length) {
    return (
      <div style={{ textAlign: "center", padding: "48px 16px" }}>
        <Images
          size={32}
          style={{ color: "var(--tg-theme-hint-color, #aaa)", marginBottom: 10 }}
        />
        <p style={{ fontSize: 15 }}>Пока нет генераций</p>
        <p style={{ fontSize: 13, color: "var(--tg-theme-hint-color, #888)" }}>
          Создайте первую в боте: /image закат над морем
        </p>
      </div>
    );
  }

  return (
    <>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>
        Мои генерации
      </h2>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 10,
        }}
      >
        {files.map((f) => (
          <div
            key={f.id}
            style={{
              borderRadius: 12,
              overflow: "hidden",
              background: "var(--tg-theme-secondary-bg-color, #f5f5f5)",
            }}
          >
            {f.media_type === "video" ? (
              <video
                src={f.url}
                muted
                playsInline
                style={{ width: "100%", aspectRatio: "1", objectFit: "cover" }}
              />
            ) : (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={f.url}
                alt={f.prompt}
                loading="lazy"
                style={{ width: "100%", aspectRatio: "1", objectFit: "cover" }}
              />
            )}
            <div style={{ display: "flex", padding: 6, gap: 6 }}>
              <GalleryBtn
                onClick={() => {
                  haptic("light");
                  downloadFile(
                    f.url,
                    `aineron_${f.id}.${f.media_type === "video" ? "mp4" : "png"}`
                  );
                }}
              >
                <Download size={15} />
              </GalleryBtn>
              <GalleryBtn
                disabled={busyId === f.id}
                onClick={() => handleShare(f)}
              >
                <Share2 size={15} />
              </GalleryBtn>
              {f.media_type !== "video" && (
                <GalleryBtn
                  onClick={() => {
                    haptic("medium");
                    if (!shareToStory(f.url, BOT_USERNAME)) {
                      window.open(f.url, "_blank");
                    }
                  }}
                >
                  <span style={{ fontSize: 11, fontWeight: 600 }}>Стори</span>
                </GalleryBtn>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function GalleryBtn({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "7px 0",
        borderRadius: 8,
        border: "none",
        background: "var(--tg-theme-bg-color, #fff)",
        color: "var(--tg-theme-accent-text-color, #C4623E)",
        cursor: "pointer",
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {children}
    </button>
  );
}

// ─── Чат ───

interface ChatMsg {
  role: "user" | "assistant";
  text: string;
  pending?: boolean;
}

function ChatScreen({ token }: { token: string }) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [chatId, setChatId] = useState<number | null>(null);
  const [sending, setSending] = useState(false);
  const [networkSlug, setNetworkSlug] = useState<string>("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Самая дешёвая текстовая модель по умолчанию
    fetch("/api/v1/catalog/networks/")
      .then((r) => r.json())
      .then((data) => {
        const nets = Array.isArray(data) ? data : (data.networks ?? data.results ?? []);
        const text = nets.find(
          (n: { provider?: string; slug?: string }) => n.provider === "openrouter"
        );
        if (text?.slug) setNetworkSlug(text.slug);
        else if (nets[0]?.slug) setNetworkSlug(nets[0].slug);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const poll = useCallback(
    async (messageId: number) => {
      for (let i = 0; i < 75; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          const msg = await api<{ status: string; plain_text?: string; content?: string }>(
            `/messages/${messageId}/status/`,
            token
          );
          if (msg.status === "completed") {
            const text = msg.plain_text || msg.content || "";
            setMessages((prev) =>
              prev.map((m, idx) =>
                idx === prev.length - 1 ? { role: "assistant", text } : m
              )
            );
            haptic("success");
            return;
          }
          if (msg.status === "failed") {
            setMessages((prev) =>
              prev.map((m, idx) =>
                idx === prev.length - 1
                  ? { role: "assistant", text: "Ошибка генерации. Попробуйте ещё раз." }
                  : m
              )
            );
            return;
          }
        } catch {
          /* keep polling */
        }
      }
    },
    [token]
  );

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || sending || !networkSlug) return;
    haptic("light");
    setSending(true);
    setInput("");
    setMessages((prev) => [
      ...prev,
      { role: "user", text },
      { role: "assistant", text: "Думаю...", pending: true },
    ]);
    try {
      let assistantId: number;
      if (chatId == null) {
        const res = await api<{ chat_id: number; assistant_message_id: number }>(
          "/chats/",
          token,
          {
            method: "POST",
            body: JSON.stringify({ network_slug: networkSlug, message: text }),
          }
        );
        setChatId(res.chat_id);
        assistantId = res.assistant_message_id;
      } else {
        const res = await api<{ assistant_message_id: number }>(
          `/chats/${chatId}/messages/`,
          token,
          { method: "POST", body: JSON.stringify({ message: text }) }
        );
        assistantId = res.assistant_message_id;
      }
      await poll(assistantId);
    } catch (e) {
      setMessages((prev) =>
        prev.map((m, idx) =>
          idx === prev.length - 1
            ? {
                role: "assistant",
                text: e instanceof Error ? e.message : "Ошибка отправки",
              }
            : m
        )
      );
    } finally {
      setSending(false);
    }
  }, [input, sending, networkSlug, chatId, token, poll]);

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "70vh" }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 12 }}>Чат с AI</h2>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
        {messages.length === 0 && (
          <p
            style={{
              fontSize: 14,
              color: "var(--tg-theme-hint-color, #888)",
              textAlign: "center",
              padding: "32px 0",
            }}
          >
            Задайте вопрос — AI ответит прямо здесь.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "85%",
              padding: "10px 13px",
              borderRadius: 14,
              fontSize: 15,
              lineHeight: 1.45,
              whiteSpace: "pre-wrap",
              background:
                m.role === "user"
                  ? "var(--tg-theme-button-color, #C4623E)"
                  : "var(--tg-theme-secondary-bg-color, #f5f5f5)",
              color:
                m.role === "user"
                  ? "var(--tg-theme-button-text-color, #fff)"
                  : "var(--tg-theme-text-color, #000)",
              opacity: m.pending ? 0.6 : 1,
            }}
          >
            {m.text}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div
        style={{
          display: "flex",
          gap: 8,
          marginTop: 12,
          position: "sticky",
          bottom: 76,
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ваш вопрос..."
          style={{
            flex: 1,
            padding: "11px 14px",
            borderRadius: 12,
            border: "1px solid var(--tg-theme-section-separator-color, #ddd)",
            background: "var(--tg-theme-secondary-bg-color, #f7f7f7)",
            color: "var(--tg-theme-text-color, #000)",
            fontSize: 15,
            outline: "none",
          }}
        />
        <button
          onClick={send}
          disabled={sending || !input.trim()}
          style={{
            width: 44,
            height: 44,
            borderRadius: 12,
            border: "none",
            background: "var(--tg-theme-button-color, #C4623E)",
            color: "var(--tg-theme-button-text-color, #fff)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            opacity: sending || !input.trim() ? 0.5 : 1,
          }}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
