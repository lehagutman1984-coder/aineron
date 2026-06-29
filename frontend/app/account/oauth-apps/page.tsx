"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Copy, Key, ExternalLink } from "lucide-react";

interface OAuthApp {
  id: number;
  name: string;
  client_id: string;
  client_secret: string;
  redirect_uris: string;
  authorization_grant_type: string;
  created: string;
}

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "").replace(/\/$/, "");

async function oauthFetch(path: string, init: RequestInit = {}) {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init.headers as Record<string, string>) };
  const res = await fetch(`${SITE_URL}${path}`, { ...init, headers, credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res;
}

async function listOAuthApps(): Promise<OAuthApp[]> {
  const r = await oauthFetch("/oauth/applications/");
  return r.json();
}

async function createOAuthApp(data: { name: string; redirect_uris: string }): Promise<OAuthApp> {
  const r = await oauthFetch("/oauth/applications/", {
    method: "POST",
    body: JSON.stringify({ ...data, authorization_grant_type: "authorization-code", client_type: "public" }),
  });
  return r.json();
}

async function deleteOAuthApp(id: number): Promise<void> {
  await oauthFetch(`/oauth/applications/${id}/`, { method: "DELETE" });
}

export default function OAuthAppsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [redirectUris, setRedirectUris] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: apps = [], isLoading } = useQuery<OAuthApp[]>({
    queryKey: ["oauth-apps"],
    queryFn: listOAuthApps,
  });

  const create = useMutation({
    mutationFn: createOAuthApp,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["oauth-apps"] });
      setName("");
      setRedirectUris("");
      setFormOpen(false);
      setError(null);
    },
    onError: (e: Error) => setError(e.message),
  });

  const remove = useMutation({
    mutationFn: deleteOAuthApp,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["oauth-apps"] }),
  });

  function copy(text: string, id: string) {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">OAuth-приложения</h1>
          <p className="mt-1 text-[15px] text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.45)]">
            Сторонние приложения с доступом через Telegram-аутентификацию
          </p>
        </div>
        <button
          onClick={() => setFormOpen(!formOpen)}
          className="flex items-center gap-2 rounded-lg bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white hover:bg-[#C4623E]"
        >
          <Plus size={14} />
          Создать
        </button>
      </div>

      {formOpen && (
        <div className="mb-6 rounded-xl border border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] p-5 dark:border-[rgba(255,255,255,0.07)] dark:bg-[rgba(255,255,255,0.03)]">
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-[14px] font-medium text-[rgba(13,13,13,0.60)] dark:text-[rgba(236,236,236,0.50)]">
                Название приложения
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My App"
                className="w-full rounded-lg border border-[rgba(13,13,13,0.12)] bg-white px-3 py-2 text-[15px] outline-none focus:border-[#D97757] dark:border-[rgba(255,255,255,0.10)] dark:bg-[rgba(255,255,255,0.05)] dark:text-[#EDE8E3]"
              />
            </div>
            <div>
              <label className="mb-1 block text-[14px] font-medium text-[rgba(13,13,13,0.60)] dark:text-[rgba(236,236,236,0.50)]">
                Redirect URIs (по одному на строку)
              </label>
              <textarea
                value={redirectUris}
                onChange={(e) => setRedirectUris(e.target.value)}
                placeholder="https://myapp.com/auth/callback"
                rows={3}
                className="w-full rounded-lg border border-[rgba(13,13,13,0.12)] bg-white px-3 py-2 text-[15px] outline-none focus:border-[#D97757] dark:border-[rgba(255,255,255,0.10)] dark:bg-[rgba(255,255,255,0.05)] dark:text-[#EDE8E3]"
              />
            </div>
            {error && <p className="text-[14px] text-[#e74c3c]">{error}</p>}
            <div className="flex gap-2">
              <button
                onClick={() => create.mutate({ name, redirect_uris: redirectUris })}
                disabled={!name.trim() || !redirectUris.trim() || create.isPending}
                className="rounded-lg bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white disabled:opacity-50 hover:bg-[#C4623E]"
              >
                {create.isPending ? "Создание..." : "Создать"}
              </button>
              <button
                onClick={() => setFormOpen(false)}
                className="rounded-lg border border-[rgba(13,13,13,0.12)] px-4 py-2 text-[15px] text-[rgba(13,13,13,0.60)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.10)] dark:text-[rgba(236,236,236,0.50)]"
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="py-16 text-center text-[15px] text-[rgba(13,13,13,0.40)]">Загрузка...</div>
      ) : apps.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[rgba(13,13,13,0.12)] py-16 text-center dark:border-[rgba(255,255,255,0.10)]">
          <Key size={32} className="mx-auto mb-3 text-[rgba(13,13,13,0.20)] dark:text-[rgba(236,236,236,0.18)]" />
          <p className="text-[16px] text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.42)]">
            Нет OAuth-приложений
          </p>
          <p className="mt-1 text-[14px] text-[rgba(13,13,13,0.35)]">
            Создайте приложение, чтобы пользователи могли входить через Telegram
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {apps.map((app) => (
            <div
              key={app.id}
              className="rounded-xl border border-[rgba(13,13,13,0.08)] bg-white p-5 dark:border-[rgba(255,255,255,0.07)] dark:bg-[rgba(255,255,255,0.03)]"
            >
              <div className="mb-3 flex items-start justify-between">
                <div>
                  <p className="text-[16px] font-medium text-[#1A1A1A] dark:text-[#EDE8E3]">{app.name}</p>
                  <p className="mt-0.5 text-[13px] text-[rgba(13,13,13,0.40)]">
                    Создано {new Date(app.created).toLocaleDateString("ru")}
                  </p>
                </div>
                <button
                  onClick={() => remove.mutate(app.id)}
                  className="text-[rgba(13,13,13,0.35)] hover:text-[#e74c3c] dark:text-[rgba(236,236,236,0.30)]"
                >
                  <Trash2 size={15} />
                </button>
              </div>
              <div className="space-y-2">
                <CredentialRow
                  label="Client ID"
                  value={app.client_id}
                  copied={copiedId === `cid-${app.id}`}
                  onCopy={() => copy(app.client_id, `cid-${app.id}`)}
                />
                <CredentialRow
                  label="Client Secret"
                  value={app.client_secret}
                  copied={copiedId === `cs-${app.id}`}
                  onCopy={() => copy(app.client_secret, `cs-${app.id}`)}
                  secret
                />
                <div>
                  <span className="text-[13px] text-[rgba(13,13,13,0.40)]">Redirect URIs</span>
                  <p className="mt-0.5 text-[14px] text-[rgba(13,13,13,0.70)] dark:text-[rgba(236,236,236,0.60)]">
                    {app.redirect_uris || "—"}
                  </p>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <a
                  href={`/oauth/authorize/?client_id=${app.client_id}&response_type=code&scope=profile`}
                  target="_blank"
                  className="flex items-center gap-1 text-[14px] text-[#D97757] hover:underline"
                >
                  <ExternalLink size={12} />
                  Тест авторизации
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CredentialRow({
  label,
  value,
  copied,
  onCopy,
  secret,
}: {
  label: string;
  value: string;
  copied: boolean;
  onCopy: () => void;
  secret?: boolean;
}) {
  const [show, setShow] = useState(!secret);
  const display = show ? value : "•".repeat(Math.min(value.length, 32));
  return (
    <div>
      <span className="text-[13px] text-[rgba(13,13,13,0.40)]">{label}</span>
      <div className="mt-0.5 flex items-center gap-2">
        <code className="flex-1 rounded bg-[rgba(13,13,13,0.04)] px-2 py-1 text-[13px] font-mono text-[#1A1A1A] dark:bg-[rgba(255,255,255,0.06)] dark:text-[#EDE8E3]">
          {display}
        </code>
        {secret && (
          <button
            onClick={() => setShow(!show)}
            className="text-[rgba(13,13,13,0.35)] hover:text-[#1A1A1A] dark:hover:text-[#EDE8E3]"
          >
            {show ? <span className="text-[13px]">скрыть</span> : <span className="text-[13px]">показать</span>}
          </button>
        )}
        <button onClick={onCopy} className="text-[rgba(13,13,13,0.35)] hover:text-[#D97757]">
          {copied ? (
            <span className="text-[13px] text-[#22c55e]">скопировано</span>
          ) : (
            <Copy size={13} />
          )}
        </button>
      </div>
    </div>
  );
}
