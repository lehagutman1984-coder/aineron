"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Copy, Key, Eye, EyeOff } from "lucide-react";
import { listAPIKeys, createAPIKey, deleteAPIKey } from "@/lib/api/client";
import { APIError } from "@/lib/api/client";
import type { APIKey } from "@/lib/api/types";

export default function KeysPage() {
  const qc = useQueryClient();
  const [newKeyName, setNewKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: keys = [], isLoading } = useQuery<APIKey[]>({
    queryKey: ["api-keys"],
    queryFn: listAPIKeys,
  });

  const createMutation = useMutation({
    mutationFn: () => createAPIKey({ name: newKeyName.trim() }),
    onSuccess: (res) => {
      setCreatedKey(res.key);
      setNewKeyName("");
      setFormOpen(false);
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
    onError: (err) => {
      setError(err instanceof APIError ? err.message : "Ошибка создания ключа");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteAPIKey(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setError(null);
    createMutation.mutate();
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <h1 className="mb-8 text-[22px] font-bold text-[#1A1A1A]">API-ключи</h1>

      {/* Created key banner */}
      {createdKey && (
        <div className="mb-6 rounded-[12px] border border-[rgba(217,119,87,0.35)] bg-[rgba(217,119,87,0.08)] p-5">
          <p className="mb-2 text-[13px] font-semibold text-[#D97757]">
            Ключ создан. Сохраните — он показывается только один раз.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 truncate rounded-[6px] border border-[rgba(13,13,13,0.15)] bg-white px-3 py-2 text-[12px] text-[#1A1A1A]">
              {showKey ? createdKey : "•".repeat(Math.min(createdKey.length, 40))}
            </code>
            <button
              onClick={() => setShowKey((v) => !v)}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px] border border-[rgba(13,13,13,0.15)] bg-white text-[rgba(13,13,13,0.5)] hover:text-[#1A1A1A] transition-all"
            >
              {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
            <button
              onClick={() => handleCopy(createdKey)}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px] border border-[rgba(13,13,13,0.15)] bg-white text-[rgba(13,13,13,0.5)] hover:text-[#1A1A1A] transition-all"
            >
              <Copy size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Create form */}
      {formOpen ? (
        <form
          onSubmit={handleCreate}
          className="mb-5 flex items-end gap-3 rounded-[12px] border border-[rgba(13,13,13,0.12)] bg-white p-4"
        >
          <div className="flex-1">
            <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.6)]">
              Название ключа
            </label>
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Например: VS Code, Cursor, Prod"
              autoFocus
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[14px] text-[#1A1A1A] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
            />
          </div>
          <button
            type="submit"
            disabled={!newKeyName.trim() || createMutation.isPending}
            className="h-9 rounded-[8px] bg-[#D97757] px-4 text-[13px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors"
          >
            {createMutation.isPending ? "Создание..." : "Создать"}
          </button>
          <button
            type="button"
            onClick={() => { setFormOpen(false); setError(null); }}
            className="h-9 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 text-[13px] text-[rgba(13,13,13,0.6)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            Отмена
          </button>
        </form>
      ) : (
        <button
          onClick={() => setFormOpen(true)}
          className="mb-5 flex items-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-4 py-2.5 text-[13px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] hover:text-[#1A1A1A] transition-colors"
        >
          <Plus size={15} />
          Создать ключ
        </button>
      )}

      {error && (
        <p className="mb-4 text-[13px] text-[#e74c3c]">{error}</p>
      )}

      {/* Keys list */}
      {isLoading ? (
        <div className="py-8 text-center text-[14px] text-[rgba(13,13,13,0.45)]">Загрузка...</div>
      ) : keys.length === 0 ? (
        <div className="rounded-[12px] border border-dashed border-[rgba(13,13,13,0.18)] py-12 text-center">
          <Key size={28} className="mx-auto mb-3 text-[rgba(13,13,13,0.25)]" />
          <p className="text-[14px] text-[rgba(13,13,13,0.5)]">Нет API-ключей</p>
          <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.38)]">
            Создайте ключ для подключения к IDE или вашему приложению
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {keys.map((key) => (
            <KeyRow
              key={key.id}
              apiKey={key}
              onDelete={() => deleteMutation.mutate(key.id)}
              deleting={deleteMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Info block */}
      <div className="mt-8 rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.02)] p-5 text-[13px] leading-relaxed text-[rgba(13,13,13,0.6)]">
        <p className="mb-1 font-medium text-[#1A1A1A]">Как использовать</p>
        <p>
          Base URL:{" "}
          <code className="rounded-[4px] bg-white px-1.5 py-0.5 text-[12px] border border-[rgba(13,13,13,0.12)]">
            https://aineron.ru/api/v1
          </code>
        </p>
        <p className="mt-1">
          Header:{" "}
          <code className="rounded-[4px] bg-white px-1.5 py-0.5 text-[12px] border border-[rgba(13,13,13,0.12)]">
            Authorization: Bearer ak_...
          </code>
        </p>
        <Link href="/api-docs/" className="mt-2 inline-block text-[#D97757] hover:underline underline-offset-2">
          Полная документация
        </Link>
      </div>
    </div>
  );
}

function KeyRow({
  apiKey,
  onDelete,
  deleting,
}: {
  apiKey: APIKey;
  onDelete: () => void;
  deleting: boolean;
}) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="flex items-center gap-3 rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-white px-4 py-3">
      <Key size={15} className="shrink-0 text-[rgba(13,13,13,0.4)]" />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-[#1A1A1A]">{apiKey.name}</p>
        <p className="text-[12px] text-[rgba(13,13,13,0.45)]">
          {apiKey.key_prefix}... · создан{" "}
          {new Date(apiKey.created_at).toLocaleDateString("ru-RU")}
          {apiKey.last_used_at &&
            ` · использован ${new Date(apiKey.last_used_at).toLocaleDateString("ru-RU")}`}
        </p>
      </div>
      {confirming ? (
        <div className="flex items-center gap-2">
          <span className="text-[12px] text-[rgba(13,13,13,0.5)]">Удалить?</span>
          <button
            onClick={() => { onDelete(); setConfirming(false); }}
            disabled={deleting}
            className="rounded-[6px] bg-[#e74c3c] px-2.5 py-1 text-[12px] font-medium text-white hover:bg-[#c0392b] disabled:opacity-50 transition-colors"
          >
            Да
          </button>
          <button
            onClick={() => setConfirming(false)}
            className="rounded-[6px] border border-[rgba(13,13,13,0.15)] px-2.5 py-1 text-[12px] text-[rgba(13,13,13,0.6)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            Нет
          </button>
        </div>
      ) : (
        <button
          onClick={() => setConfirming(true)}
          className="flex h-7 w-7 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.35)] hover:bg-[rgba(231,76,60,0.08)] hover:text-[#e74c3c] transition-all"
        >
          <Trash2 size={14} />
        </button>
      )}
    </div>
  );
}
