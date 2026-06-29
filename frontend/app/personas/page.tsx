"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { User, Plus, Trash2, Bot, X, Check } from "lucide-react";
import Link from "next/link";
import { listPersonas, createPersona, deletePersona } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";
import type { Persona } from "@/lib/api/types";

export default function PersonasPage() {
  const { user } = useAuthStore();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", system_prompt: "", avatar_url: "" });
  const [formErr, setFormErr] = useState("");

  const { data: personas = [], isLoading } = useQuery({
    queryKey: ["personas"],
    queryFn: listPersonas,
  });

  const createMutation = useMutation({
    mutationFn: createPersona,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["personas"] });
      setShowCreate(false);
      setForm({ name: "", description: "", system_prompt: "", avatar_url: "" });
      setFormErr("");
    },
    onError: (e: Error) => setFormErr(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: deletePersona,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["personas"] }),
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { setFormErr("Введите имя персоны"); return; }
    if (!form.system_prompt.trim()) { setFormErr("Введите системный промт"); return; }
    setFormErr("");
    createMutation.mutate(form);
  };

  const systemPersonas = personas.filter((p) => p.is_public && !p.is_own);
  const myPersonas = personas.filter((p) => p.is_own);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-[24px] font-bold text-[#1A1A1A] dark:text-[#EDE8E3]">
            AI-персоны
          </h1>
          <p className="mt-1 text-[14px] text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.45)]">
            Выберите персонажа — бот возьмёт его роль и стиль общения
          </p>
        </div>
        {user && (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 rounded-[10px] px-4 py-2 text-[13px] font-semibold text-white transition-all hover:opacity-90"
            style={{ background: "#1A1A1A" }}
          >
            <Plus size={14} />
            Создать персону
          </button>
        )}
      </div>

      {isLoading && (
        <div className="text-center py-12 text-[rgba(13,13,13,0.40)]">Загрузка...</div>
      )}

      {/* System personas */}
      {systemPersonas.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-[rgba(13,13,13,0.42)] dark:text-[rgba(236,236,236,0.40)]">
            Системные персоны
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {systemPersonas.map((p) => (
              <PersonaCard key={p.id} persona={p} />
            ))}
          </div>
        </section>
      )}

      {/* My personas */}
      {user && (
        <section>
          <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-[rgba(13,13,13,0.42)] dark:text-[rgba(236,236,236,0.40)]">
            Мои персоны
          </h2>
          {myPersonas.length === 0 ? (
            <div className="rounded-[12px] border border-dashed border-[rgba(13,13,13,0.15)] px-6 py-8 text-center dark:border-[rgba(255,255,255,0.10)]">
              <Bot size={28} className="mx-auto mb-2 text-[rgba(13,13,13,0.25)] dark:text-[rgba(236,236,236,0.25)]" />
              <p className="text-[13px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.40)]">
                У вас нет персональных персон. Создайте первую!
              </p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {myPersonas.map((p) => (
                <PersonaCard
                  key={p.id}
                  persona={p}
                  onDelete={() => deleteMutation.mutate(p.id)}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div
            className="relative mx-4 w-full max-w-lg rounded-[16px] p-6 shadow-2xl"
            style={{ background: "var(--surface, #fff)" }}
          >
            <button
              onClick={() => setShowCreate(false)}
              className="absolute right-4 top-4 rounded-[6px] p-1 text-[rgba(13,13,13,0.40)] hover:bg-[rgba(13,13,13,0.06)]"
            >
              <X size={16} />
            </button>
            <h2 className="mb-4 text-[17px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
              Новая персона
            </h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="mb-1 block text-[12px] font-medium text-[rgba(13,13,13,0.60)]">
                  Имя
                </label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Например: Дружелюбный ментор"
                  className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-transparent px-3 py-2 text-[13px] outline-none focus:border-[#D97757]"
                />
              </div>
              <div>
                <label className="mb-1 block text-[12px] font-medium text-[rgba(13,13,13,0.60)]">
                  Описание (опционально)
                </label>
                <input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Одна строка о персоне"
                  className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-transparent px-3 py-2 text-[13px] outline-none focus:border-[#D97757]"
                />
              </div>
              <div>
                <label className="mb-1 block text-[12px] font-medium text-[rgba(13,13,13,0.60)]">
                  Системный промт
                </label>
                <textarea
                  value={form.system_prompt}
                  onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                  rows={5}
                  placeholder="Ты — дружелюбный ментор по программированию..."
                  className="w-full resize-none rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-transparent px-3 py-2 text-[13px] outline-none focus:border-[#D97757]"
                />
              </div>
              {formErr && (
                <p className="text-[12px] text-[#e74c3c]">{formErr}</p>
              )}
              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="rounded-[8px] border border-[rgba(13,13,13,0.15)] px-4 py-2 text-[13px] text-[rgba(13,13,13,0.60)] hover:bg-[rgba(13,13,13,0.04)]"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="rounded-[8px] px-4 py-2 text-[13px] font-semibold text-white transition-opacity disabled:opacity-60"
                  style={{ background: "#1A1A1A" }}
                >
                  {createMutation.isPending ? "Создание..." : "Создать"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function PersonaCard({ persona, onDelete }: { persona: Persona; onDelete?: () => void }) {
  return (
    <div
      className="group relative flex flex-col gap-2 rounded-[12px] border p-4 transition-shadow hover:shadow-md"
      style={{
        background: "var(--surface, #fff)",
        borderColor: "rgba(13,13,13,0.09)",
      }}
    >
      <div className="flex items-start gap-3">
        {persona.avatar_url ? (
          <img
            src={persona.avatar_url}
            alt={persona.name}
            width={36}
            height={36}
            className="shrink-0 rounded-[8px] object-cover"
          />
        ) : (
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-[rgba(10,124,255,0.10)] text-[#D97757]">
            <Bot size={18} />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-[14px] text-[#1A1A1A] dark:text-[#EDE8E3]">
            {persona.name}
          </p>
          {persona.description && (
            <p className="mt-0.5 text-[12px] text-[rgba(13,13,13,0.52)] dark:text-[rgba(236,236,236,0.45)] line-clamp-2">
              {persona.description}
            </p>
          )}
        </div>
      </div>

      <p className="line-clamp-3 text-[11px] leading-relaxed text-[rgba(13,13,13,0.42)] dark:text-[rgba(236,236,236,0.38)] font-mono border-t border-[rgba(13,13,13,0.06)] pt-2 mt-1">
        {persona.system_prompt}
      </p>

      {onDelete && (
        <button
          onClick={onDelete}
          className="absolute right-3 top-3 hidden h-7 w-7 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.35)] transition-colors hover:bg-[rgba(231,76,60,0.08)] hover:text-[#e74c3c] group-hover:flex"
          title="Удалить персону"
        >
          <Trash2 size={13} />
        </button>
      )}
    </div>
  );
}
