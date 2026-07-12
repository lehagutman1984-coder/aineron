"use client";

/**
 * Sandbox Playground — выполнить сниппет кода в изолированной microVM.
 * Полный цикл на каждом запуске: create → exec → delete (списание ~1 минута).
 */
import { useCallback, useRef, useState } from "react";
import { Link } from "@/i18n/navigation";

import { Box, Key, Globe, Loader, Play, Square } from "lucide-react";
import { useTranslations } from "next-intl";
import { formatMoney } from "@/lib/money";
import { IS_RU } from "@/lib/site";

type AuthMode = "session" | "apikey";

const TEMPLATES = [
  { id: "python", label: "Python 3.11", language: "python", placeholder: IS_RU ? 'print("Привет из microVM")' : 'print("Hello from microVM")' },
  { id: "base", label: "Base (Python + Node)", language: "python", placeholder: 'print(2 + 2)' },
  { id: "nodejs", label: "Node.js 20", language: "node", placeholder: 'console.log(process.version)' },
];

type RunPhase = "idle" | "creating" | "executing" | "cleanup" | "done" | "error";

interface ExecOut {
  exit_code: number;
  stdout: string;
  stderr: string;
  duration_ms: number;
  truncated: boolean;
}

export function SandboxPlayground() {
  const t = useTranslations("sandbox.playground");
  const [authMode, setAuthMode] = useState<AuthMode>("session");
  const [apiKey, setApiKey] = useState("");
  const [template, setTemplate] = useState("python");
  const [code, setCode] = useState("");
  const [phase, setPhase] = useState<RunPhase>("idle");
  const [result, setResult] = useState<ExecOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cancelRef = useRef(false);

  const tpl = TEMPLATES.find((t) => t.id === template) ?? TEMPLATES[0];

  const headers = useCallback((): Record<string, string> => {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (authMode === "apikey" && apiKey.trim()) {
      h["Authorization"] = `Bearer ${apiKey.trim()}`;
    }
    return h;
  }, [authMode, apiKey]);

  const call = useCallback(
    async (method: string, path: string, body?: unknown) => {
      const res = await fetch(`/api/v1/sandboxes/${path}`, {
        method,
        headers: headers(),
        credentials: authMode === "session" ? "include" : "omit",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const json = (await res.json().catch(() => ({}))) as {
        error?: { message?: string };
      } & Record<string, unknown>;
      if (!res.ok) {
        throw new Error(json.error?.message ?? `HTTP ${res.status}`);
      }
      return json;
    },
    [headers, authMode]
  );

  const run = useCallback(async () => {
    if (phase === "creating" || phase === "executing") {
      cancelRef.current = true;
      return;
    }
    if (!code.trim()) return;
    cancelRef.current = false;
    setResult(null);
    setError(null);
    setPhase("creating");

    let sandboxId: string | null = null;
    try {
      const created = await call("POST", "", {
        template,
        size: "small",
        timeout_seconds: 120,
        metadata: { source: "playground" },
      });
      sandboxId = created.id as string;
      if (cancelRef.current) throw new Error(t("stopped"));

      setPhase("executing");
      const exec = (await call("POST", `${sandboxId}/exec/`, {
        code,
        language: tpl.language,
        timeout_seconds: 60,
      })) as unknown as ExecOut;
      setResult(exec);
      setPhase("done");
    } catch (err) {
      setError((err as Error).message);
      setPhase("error");
    } finally {
      if (sandboxId) {
        setPhase((p) => (p === "done" || p === "error" ? p : "cleanup"));
        try {
          await call("DELETE", `${sandboxId}/`);
        } catch {
          /* reconcile закроет */
        }
      }
    }
  }, [phase, code, call, template, tpl.language]);

  const busy = phase === "creating" || phase === "executing" || phase === "cleanup";

  const phaseLabel: Record<RunPhase, string> = {
    idle: "",
    creating: t("phaseCreating"),
    executing: t("phaseExecuting"),
    cleanup: t("phaseCleanup"),
    done: "",
    error: "",
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1fr]">
      {/* LEFT */}
      <div className="flex flex-col gap-4">
        {/* Auth */}
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
          <p className="mb-3 text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
            {t("auth")}
          </p>
          <div className="flex gap-2">
            {(["session", "apikey"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setAuthMode(mode)}
                className={[
                  "flex flex-1 items-center justify-center gap-1.5 rounded-[8px] border py-2 text-[15px] font-medium transition-colors",
                  authMode === mode
                    ? "border-[#D97757] bg-[rgba(217,119,87,0.06)] text-[#D97757]"
                    : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.55)] hover:border-[rgba(13,13,13,0.25)]",
                ].join(" ")}
              >
                {mode === "session" ? <Globe size={13} /> : <Key size={13} />}
                {mode === "session" ? t("session") : t("apiKeyMode")}
              </button>
            ))}
          </div>
          {authMode === "apikey" && (
            <input
              type="text"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={t("apiKeyPlaceholder")}
              spellCheck={false}
              className="mt-3 w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-3 py-2 font-mono text-[15px] text-[#1A1A1A] placeholder:text-[rgba(13,13,13,0.35)] focus:border-[#D97757] focus:outline-none"
            />
          )}
        </div>

        {/* Template */}
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
          <p className="mb-3 text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
            {t("template")}
          </p>
          <select
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-3 py-2 text-[15px] text-[#1A1A1A] focus:border-[#D97757] focus:outline-none"
          >
            {TEMPLATES.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {/* Code */}
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
          <p className="mb-3 text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
            {t("code")}
          </p>
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            rows={10}
            spellCheck={false}
            placeholder={tpl.placeholder}
            className="w-full resize-y rounded-[8px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.02)] px-3 py-2 font-mono text-[14px] leading-relaxed text-[#1A1A1A] placeholder:text-[rgba(13,13,13,0.30)] focus:border-[#D97757] focus:outline-none"
          />
        </div>

        <button
          onClick={() => void run()}
          disabled={!busy && !code.trim()}
          className={[
            "flex h-11 w-full items-center justify-center gap-2 rounded-[10px] text-[16px] font-semibold text-white transition-colors disabled:opacity-50",
            busy ? "bg-[#dc2626] hover:bg-[#b91c1c]" : "bg-[#D97757] hover:bg-[#C4623E]",
          ].join(" ")}
        >
          {busy ? (
            <>
              <Square size={15} />
              {t("stop")}
            </>
          ) : (
            <>
              <Play size={15} />
              {t("run")}
            </>
          )}
        </button>
        <p className="text-center text-[13px] text-[rgba(13,13,13,0.40)]">
          {t("billingNote", { price: formatMoney(50) })}
        </p>
      </div>

      {/* RIGHT */}
      <div className="flex flex-col gap-3">
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white">
          <div className="flex items-center justify-between border-b border-[rgba(13,13,13,0.08)] px-4 py-3">
            <span className="text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
              {t("result")}
            </span>
            {result && (
              <span
                className={`font-mono text-[14px] font-semibold ${
                  result.exit_code === 0 ? "text-[#16a34a]" : "text-[#dc2626]"
                }`}
              >
                exit {result.exit_code} · {result.duration_ms}ms
              </span>
            )}
          </div>
          <div className="min-h-[300px] p-4">
            {busy && (
              <div className="flex items-center gap-2 text-[15px] text-[rgba(13,13,13,0.45)]">
                <Loader size={14} className="animate-spin" />
                {phaseLabel[phase]}
              </div>
            )}
            {phase === "idle" && (
              <div className="flex h-full min-h-[260px] flex-col items-center justify-center text-center">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-[12px] bg-[rgba(217,119,87,0.08)]">
                  <Box size={20} className="text-[#D97757]" />
                </div>
                <p className="text-[15px] text-[rgba(13,13,13,0.45)]">
                  {t("emptyHint")}
                </p>
              </div>
            )}
            {error && (
              <p className="whitespace-pre-wrap text-[15px] text-[#dc2626]">{error}</p>
            )}
            {result && (
              <div className="flex flex-col gap-3">
                {result.stdout && (
                  <div>
                    <p className="mb-1 text-[13px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.40)]">
                      stdout
                    </p>
                    <pre className="overflow-x-auto rounded-[8px] bg-[#1A1A1A] p-3 font-mono text-[13px] leading-relaxed text-[#e4e4e4]">
                      {result.stdout}
                    </pre>
                  </div>
                )}
                {result.stderr && (
                  <div>
                    <p className="mb-1 text-[13px] font-medium uppercase tracking-wide text-[#dc2626]">
                      stderr
                    </p>
                    <pre className="overflow-x-auto rounded-[8px] bg-[rgba(220,38,38,0.06)] p-3 font-mono text-[13px] leading-relaxed text-[#b91c1c]">
                      {result.stderr}
                    </pre>
                  </div>
                )}
                {!result.stdout && !result.stderr && (
                  <p className="text-[15px] text-[rgba(13,13,13,0.45)]">{t("emptyOutput")}</p>
                )}
                {result.truncated && (
                  <p className="text-[13px] text-[rgba(13,13,13,0.40)]">
                    {t("truncated")}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/account/keys/"
            className="inline-flex items-center gap-1.5 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 py-1.5 text-[14px] text-[rgba(13,13,13,0.55)] transition-colors hover:bg-[rgba(13,13,13,0.04)] hover:text-[#1A1A1A]"
          >
            <Key size={12} />
            {t("keysLink")}
          </Link>
          <Link
            href="/sandbox/"
            className="inline-flex items-center gap-1.5 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 py-1.5 text-[14px] text-[rgba(13,13,13,0.55)] transition-colors hover:bg-[rgba(13,13,13,0.04)] hover:text-[#1A1A1A]"
          >
            <Box size={12} />{t("aboutLink")}
          </Link>
        </div>
      </div>
    </div>
  );
}
