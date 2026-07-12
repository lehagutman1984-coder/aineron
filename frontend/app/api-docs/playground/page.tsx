"use client";

import { useState, useRef, useCallback } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import {
  Play,
  Square,
  Plus,
  Trash2,
  Copy,
  Check,
  Loader,
  ChevronDown,
  ChevronRight,
  ArrowLeft,
  Key,
  Globe,
  MessageSquare,
  Box,
} from "lucide-react";
import { SandboxPlayground } from "@/components/docs/SandboxPlayground";
import { IS_RU } from "@/lib/site";

// Плейсхолдер API-ключа в примерах — по локали инстанса
const KEY_PLACEHOLDER = IS_RU ? "ak_ВАШ_КЛЮЧ" : "ak_YOUR_KEY";

// Реальный base_url текущего инстанса (aineron.ru / aineron.net), не хардкод.
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "https://aineron.ru/api/v1";

const PRESET_MODELS = [
  { id: "gpt-4o", label: "GPT-4o" },
  { id: "gpt-4o-mini", label: "GPT-4o Mini" },
  { id: "gpt-4.1", label: "GPT-4.1" },
  { id: "claude-3-5-sonnet-20241022", label: "Claude 3.5 Sonnet" },
  { id: "claude-3-haiku-20240307", label: "Claude 3 Haiku" },
  { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
  { id: "gemini-1.5-pro", label: "Gemini 1.5 Pro" },
  { id: "deepseek-v3", label: "DeepSeek V3" },
  { id: "deepseek-r1", label: "DeepSeek R1" },
  { id: "custom", label: null },
];

type Role = "user" | "assistant";
type Message = { id: number; role: Role; content: string };
type AuthMode = "session" | "apikey";

let msgId = 1;

function makeMsg(role: Role, content = ""): Message {
  return { id: msgId++, role, content };
}

function RoleTag({ role, onChange }: { role: Role; onChange: () => void }) {
  const t = useTranslations("apiDocsPlayground");
  return (
    <button
      onClick={onChange}
      title={t("toggleRoleTooltip")}
      className={[
        "shrink-0 rounded-[5px] px-2 py-0.5 text-[13px] font-medium uppercase tracking-wide transition-colors",
        role === "user"
          ? "bg-[rgba(217,119,87,0.10)] text-[#D97757]"
          : "bg-[rgba(13,13,13,0.06)] text-[rgba(13,13,13,0.55)]",
      ].join(" ")}
    >
      {role === "user" ? "user" : "assistant"}
    </button>
  );
}

export default function PlaygroundPage() {
  const t = useTranslations("apiDocsPlayground");
  const [playgroundTab, setPlaygroundTab] = useState<"chat" | "sandbox">("chat");
  const [authMode, setAuthMode] = useState<AuthMode>("session");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("gpt-4o");
  const [customModel, setCustomModel] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [sysOpen, setSysOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([makeMsg("user")]);
  const [temperature, setTemperature] = useState(1.0);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [streamMode, setStreamMode] = useState(false);

  const [loading, setLoading] = useState(false);
  const [resText, setResText] = useState<string | null>(null);
  const [resJson, setResJson] = useState<string | null>(null);
  const [resStatus, setResStatus] = useState<number | null>(null);
  const [resTime, setResTime] = useState<number | null>(null);
  const [resTab, setResTab] = useState<"formatted" | "json">("formatted");
  const [copied, setCopied] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  const addMessage = () =>
    setMessages((m) => [
      ...m,
      makeMsg(m[m.length - 1]?.role === "user" ? "assistant" : "user"),
    ]);

  const removeMessage = (id: number) =>
    setMessages((m) => (m.length > 1 ? m.filter((x) => x.id !== id) : m));

  const updateMessage = (id: number, field: keyof Message, value: string) =>
    setMessages((m) =>
      m.map((x) => (x.id === id ? { ...x, [field]: value } : x))
    );

  const toggleRole = (id: number) =>
    setMessages((m) =>
      m.map((x) =>
        x.id === id
          ? { ...x, role: x.role === "user" ? "assistant" : "user" }
          : x
      )
    );

  const execute = useCallback(async () => {
    if (loading) {
      abortRef.current?.abort();
      setLoading(false);
      return;
    }

    const effectiveModel = model === "custom" ? customModel.trim() : model;
    if (!effectiveModel) return;

    const validMessages = messages.filter((m) => m.content.trim());
    if (validMessages.length === 0) return;

    setLoading(true);
    setResText(null);
    setResJson(null);
    setResStatus(null);
    setResTime(null);

    const t0 = Date.now();
    abortRef.current = new AbortController();

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (authMode === "apikey" && apiKey.trim()) {
      headers["Authorization"] = `Bearer ${apiKey.trim()}`;
    }

    const body = {
      model: effectiveModel,
      messages: [
        ...(systemPrompt.trim()
          ? [{ role: "system", content: systemPrompt.trim() }]
          : []),
        ...validMessages.map((m) => ({ role: m.role, content: m.content })),
      ],
      temperature,
      max_tokens: maxTokens,
      stream: streamMode,
    };

    try {
      const res = await fetch("/api/v1/chat/completions", {
        method: "POST",
        headers,
        credentials: authMode === "session" ? "include" : "omit",
        body: JSON.stringify(body),
        signal: abortRef.current.signal,
      });

      setResStatus(res.status);

      if (streamMode && res.ok && res.body) {
        setResText("");
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let jsonLines = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = dec.decode(value, { stream: true });
          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6).trim();
            if (data === "[DONE]") continue;
            try {
              const parsed = JSON.parse(data) as {
                choices?: Array<{ delta?: { content?: string } }>;
              };
              const delta = parsed.choices?.[0]?.delta?.content;
              if (delta) setResText((prev) => (prev ?? "") + delta);
              jsonLines += data + "\n";
            } catch {}
          }
        }
        setResJson(jsonLines.trim() || null);
        setResTime(Date.now() - t0);
      } else {
        const json: unknown = await res.json();
        setResTime(Date.now() - t0);
        setResJson(JSON.stringify(json, null, 2));
        if (res.ok) {
          const j = json as {
            choices?: Array<{ message?: { content?: string } }>;
          };
          setResText(j.choices?.[0]?.message?.content ?? null);
        } else {
          const err = json as { error?: { message?: string }; detail?: string };
          setResText(err.error?.message ?? err.detail ?? t("genericError"));
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setResTime(Date.now() - t0);
        setResText(t("networkError", { message: (err as Error).message }));
        setResJson(JSON.stringify({ error: (err as Error).message }, null, 2));
      }
    } finally {
      setLoading(false);
    }
  }, [loading, authMode, apiKey, model, customModel, systemPrompt, messages, temperature, maxTokens, streamMode, t]);

  const copyRes = () => {
    const text = resTab === "json" ? resJson : resText;
    if (!text) return;
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const statusColor =
    resStatus == null
      ? ""
      : resStatus < 300
      ? "text-[#16a34a]"
      : resStatus < 500
      ? "text-[#d97706]"
      : "text-[#dc2626]";

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <Link
          href="/api-docs/"
          className="flex items-center gap-1.5 text-[15px] text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A] transition-colors"
        >
          <ArrowLeft size={14} />
          {t("breadcrumbDocs")}
        </Link>
        <span className="text-[rgba(13,13,13,0.25)]">/</span>
        <span className="text-[15px] font-medium text-[#1A1A1A]">
          API Playground
        </span>
      </div>

      <h1 className="mb-1 text-[24px] font-bold text-[#1A1A1A]">
        API Playground
      </h1>
      <p className="mb-6 text-[16px] text-[rgba(13,13,13,0.55)]">
        {t("subtitle")}
      </p>

      {/* Tab switcher: Chat / Sandbox */}
      <div className="mb-8 flex gap-2">
        {(
          [
            { id: "chat", label: "Chat Completions", icon: MessageSquare },
            { id: "sandbox", label: "Sandboxes", icon: Box },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setPlaygroundTab(tab.id)}
            className={[
              "flex items-center gap-2 rounded-[10px] border px-4 py-2 text-[15px] font-medium transition-colors",
              playgroundTab === tab.id
                ? "border-[#D97757] bg-[rgba(217,119,87,0.06)] text-[#D97757]"
                : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.55)] hover:border-[rgba(13,13,13,0.25)]",
            ].join(" ")}
          >
            <tab.icon size={14} />
            {tab.label}
          </button>
        ))}
      </div>

      {playgroundTab === "sandbox" && <SandboxPlayground />}

      <div
        className={
          playgroundTab === "chat"
            ? "grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1fr]"
            : "hidden"
        }
      >
        {/* LEFT: Request builder */}
        <div className="flex flex-col gap-4">
          {/* Auth */}
          <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
            <p className="mb-3 text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
              {t("authSectionTitle")}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setAuthMode("session")}
                className={[
                  "flex flex-1 items-center justify-center gap-1.5 rounded-[8px] border py-2 text-[15px] font-medium transition-colors",
                  authMode === "session"
                    ? "border-[#D97757] bg-[rgba(217,119,87,0.06)] text-[#D97757]"
                    : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.55)] hover:border-[rgba(13,13,13,0.25)]",
                ].join(" ")}
              >
                <Globe size={13} />
                {t("authModeSession")}
              </button>
              <button
                onClick={() => setAuthMode("apikey")}
                className={[
                  "flex flex-1 items-center justify-center gap-1.5 rounded-[8px] border py-2 text-[15px] font-medium transition-colors",
                  authMode === "apikey"
                    ? "border-[#D97757] bg-[rgba(217,119,87,0.06)] text-[#D97757]"
                    : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.55)] hover:border-[rgba(13,13,13,0.25)]",
                ].join(" ")}
              >
                <Key size={13} />
                {t("authModeApiKey")}
              </button>
            </div>
            {authMode === "apikey" && (
              <input
                type="text"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={KEY_PLACEHOLDER}
                spellCheck={false}
                className="mt-3 w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-3 py-2 font-mono text-[15px] text-[#1A1A1A] placeholder:text-[rgba(13,13,13,0.35)] focus:border-[#D97757] focus:outline-none"
              />
            )}
            {authMode === "session" && (
              <p className="mt-2 text-[14px] text-[rgba(13,13,13,0.45)]">
                {t("authSessionHint")}
              </p>
            )}
          </div>

          {/* Model + params */}
          <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
            <p className="mb-3 text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
              {t("modelSectionTitle")}
            </p>

            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="mb-3 w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-3 py-2 text-[15px] text-[#1A1A1A] focus:border-[#D97757] focus:outline-none"
            >
              {PRESET_MODELS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label ?? t("customModelOption")}
                </option>
              ))}
            </select>

            {model === "custom" && (
              <input
                type="text"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                placeholder="gpt-4o-2024-11-20"
                className="mb-3 w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-3 py-2 font-mono text-[15px] text-[#1A1A1A] placeholder:text-[rgba(13,13,13,0.35)] focus:border-[#D97757] focus:outline-none"
              />
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label className="text-[14px] text-[rgba(13,13,13,0.55)]">
                    Temperature
                  </label>
                  <span className="text-[14px] font-mono font-medium text-[#1A1A1A]">
                    {temperature.toFixed(1)}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={2}
                  step={0.1}
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-[#D97757]"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-[14px] text-[rgba(13,13,13,0.55)]">
                  Max tokens
                </label>
                <input
                  type="number"
                  min={1}
                  max={32768}
                  value={maxTokens}
                  onChange={(e) =>
                    setMaxTokens(Math.max(1, parseInt(e.target.value) || 1))
                  }
                  className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-3 py-2 text-[15px] text-[#1A1A1A] focus:border-[#D97757] focus:outline-none"
                />
              </div>
            </div>

            <label className="mt-3 flex cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                checked={streamMode}
                onChange={(e) => setStreamMode(e.target.checked)}
                className="accent-[#D97757]"
              />
              <span className="text-[15px] text-[rgba(13,13,13,0.65)]">
                Streaming (SSE)
              </span>
            </label>
          </div>

          {/* System prompt */}
          <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white">
            <button
              onClick={() => setSysOpen((o) => !o)}
              className="flex w-full items-center justify-between px-4 py-3 text-left"
            >
              <span className="text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
                System prompt
              </span>
              {sysOpen ? (
                <ChevronDown size={14} className="text-[rgba(13,13,13,0.4)]" />
              ) : (
                <ChevronRight size={14} className="text-[rgba(13,13,13,0.4)]" />
              )}
            </button>
            {sysOpen && (
              <div className="border-t border-[rgba(13,13,13,0.08)] px-4 pb-4">
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={4}
                  placeholder={t("systemPromptPlaceholder")}
                  className="mt-3 w-full resize-none rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-3 py-2 text-[15px] text-[#1A1A1A] placeholder:text-[rgba(13,13,13,0.35)] focus:border-[#D97757] focus:outline-none"
                />
              </div>
            )}
          </div>

          {/* Messages */}
          <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
            <p className="mb-3 text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
              Messages
            </p>
            <div className="flex flex-col gap-2">
              {messages.map((msg) => (
                <div key={msg.id} className="flex items-start gap-2">
                  <div className="mt-2">
                    <RoleTag
                      role={msg.role}
                      onChange={() => toggleRole(msg.id)}
                    />
                  </div>
                  <textarea
                    value={msg.content}
                    onChange={(e) =>
                      updateMessage(msg.id, "content", e.target.value)
                    }
                    rows={2}
                    placeholder={
                      msg.role === "user"
                        ? t("userMessagePlaceholder")
                        : t("assistantMessagePlaceholder")
                    }
                    className="flex-1 resize-none rounded-[8px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.02)] px-3 py-2 text-[15px] text-[#1A1A1A] placeholder:text-[rgba(13,13,13,0.30)] focus:border-[#D97757] focus:outline-none"
                  />
                  <button
                    onClick={() => removeMessage(msg.id)}
                    disabled={messages.length === 1}
                    className="mt-2 text-[rgba(13,13,13,0.30)] hover:text-[#dc2626] transition-colors disabled:opacity-20"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
            <button
              onClick={addMessage}
              className="mt-3 flex items-center gap-1.5 text-[14px] text-[rgba(13,13,13,0.45)] hover:text-[#D97757] transition-colors"
            >
              <Plus size={13} />
              {t("addMessageButton")}
            </button>
          </div>

          {/* Execute */}
          <button
            onClick={() => void execute()}
            className={[
              "flex h-11 w-full items-center justify-center gap-2 rounded-[10px] text-[16px] font-semibold text-white transition-colors",
              loading
                ? "bg-[#dc2626] hover:bg-[#b91c1c]"
                : "bg-[#D97757] hover:bg-[#C4623E]",
            ].join(" ")}
          >
            {loading ? (
              <>
                <Square size={15} />
                {t("stopButton")}
              </>
            ) : (
              <>
                <Play size={15} />
                {t("executeButton")}
              </>
            )}
          </button>
        </div>

        {/* RIGHT: Response */}
        <div className="flex flex-col gap-3">
          <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white">
            {/* Response header */}
            <div className="flex items-center justify-between border-b border-[rgba(13,13,13,0.08)] px-4 py-3">
              <div className="flex items-center gap-3">
                <span className="text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
                  Response
                </span>
                {resStatus != null && (
                  <span
                    className={`text-[14px] font-semibold font-mono ${statusColor}`}
                  >
                    {resStatus}
                  </span>
                )}
                {resTime != null && (
                  <span className="text-[14px] text-[rgba(13,13,13,0.35)]">
                    {resTime}ms
                  </span>
                )}
              </div>
              {(resText || resJson) && (
                <button
                  onClick={copyRes}
                  className="flex items-center gap-1 text-[14px] text-[rgba(13,13,13,0.40)] hover:text-[#1A1A1A] transition-colors"
                >
                  {copied ? <Check size={13} /> : <Copy size={13} />}
                  {copied ? t("copiedLabel") : t("copyLabel")}
                </button>
              )}
            </div>

            {/* Tabs */}
            {(resText !== null || resJson !== null) && (
              <div className="flex border-b border-[rgba(13,13,13,0.06)] px-4">
                {(["formatted", "json"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setResTab(tab)}
                    className={[
                      "mr-4 border-b-2 py-2 text-[14px] font-medium transition-colors",
                      resTab === tab
                        ? "border-[#D97757] text-[#D97757]"
                        : "border-transparent text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A]",
                    ].join(" ")}
                  >
                    {tab === "formatted" ? t("responseTabLabel") : "JSON"}
                  </button>
                ))}
              </div>
            )}

            {/* Content */}
            <div className="min-h-[300px] p-4">
              {loading && resText === null && (
                <div className="flex items-center gap-2 text-[15px] text-[rgba(13,13,13,0.45)]">
                  <Loader size={14} className="animate-spin" />
                  {t("waitingForResponse")}
                </div>
              )}

              {!loading && resText === null && resJson === null && (
                <div className="flex h-full min-h-[260px] flex-col items-center justify-center text-center">
                  <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-[12px] bg-[rgba(217,119,87,0.08)]">
                    <Play size={20} className="text-[#D97757]" />
                  </div>
                  <p className="text-[15px] text-[rgba(13,13,13,0.45)]">
                    {t("emptyStateHint")}
                  </p>
                </div>
              )}

              {resTab === "formatted" && resText !== null && (
                <pre className="whitespace-pre-wrap break-words font-sans text-[15px] leading-relaxed text-[#1A1A1A]">
                  {resText}
                </pre>
              )}

              {resTab === "json" && resJson !== null && (
                <pre className="overflow-x-auto whitespace-pre font-mono text-[11.5px] leading-relaxed text-[#1A1A1A]">
                  <code>{resJson}</code>
                </pre>
              )}
            </div>
          </div>

          {/* Request preview */}
          <details className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white">
            <summary className="cursor-pointer px-4 py-3 text-[14px] font-medium text-[rgba(13,13,13,0.45)] uppercase tracking-wide hover:text-[#1A1A1A] transition-colors select-none">
              {t("curlCommandSummary")}
            </summary>
            <div className="border-t border-[rgba(13,13,13,0.06)] px-4 pb-4">
              <pre className="mt-3 overflow-x-auto rounded-[8px] bg-[#1A1A1A] p-3 font-mono text-[13px] leading-relaxed text-[#e4e4e4]">
                {[
                  `curl ${API_BASE}/chat/completions \\`,
                  authMode === "apikey"
                    ? `  -H "Authorization: Bearer ${apiKey || KEY_PLACEHOLDER}" \\`
                    : `  -H "Cookie: sessionid=..." \\`,
                  `  -H "Content-Type: application/json" \\`,
                  `  -d '${JSON.stringify(
                    {
                      model: model === "custom" ? customModel || "gpt-4o" : model,
                      messages: [
                        ...(systemPrompt.trim()
                          ? [{ role: "system", content: systemPrompt.slice(0, 50) + (systemPrompt.length > 50 ? "..." : "") }]
                          : []),
                        ...messages.slice(0, 2).map((m) => ({
                          role: m.role,
                          content: m.content.slice(0, 60) + (m.content.length > 60 ? "..." : ""),
                        })),
                      ],
                      temperature,
                      max_tokens: maxTokens,
                      ...(streamMode ? { stream: true } : {}),
                    },
                    null,
                    2
                  )
                    .split("\n")
                    .join("\n  ")}'`,
                ].join("\n")}
              </pre>
            </div>
          </details>

          {/* Links */}
          <div className="flex flex-wrap gap-2">
            <Link
              href="/account/keys/"
              className="inline-flex items-center gap-1.5 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 py-1.5 text-[14px] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.04)] hover:text-[#1A1A1A] transition-colors"
            >
              <Key size={12} />
              {t("getApiKeyLink")}
            </Link>
            <a
              href="/api/v1/docs/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 py-1.5 text-[14px] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.04)] hover:text-[#1A1A1A] transition-colors"
            >
              Swagger UI
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
