"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Bot, X, Send, MessageSquarePlus, Loader2, Cpu } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { listPersonas, createPersona, deletePersona, createChat, listNetworks } from "@/lib/api/client";
import { formatMoney } from "@/lib/money";
import { useAuthStore } from "@/lib/stores/auth";
import type { Persona, NetworkListItem } from "@/lib/api/types";

export default function PersonasPage() {
  const t = useTranslations("personas");
  const { user } = useAuthStore();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", system_prompt: "", avatar_url: "", network: "" });
  const [formErr, setFormErr] = useState("");

  const { data: personas = [], isLoading } = useQuery({
    queryKey: ["personas"],
    queryFn: listPersonas,
  });

  // Текстовые модели для выбора «модели по умолчанию» и старта чата
  const { data: textNetworks = [] } = useQuery({
    queryKey: ["networks", "text"],
    queryFn: () => listNetworks({ provider: "openrouter" }),
    staleTime: 5 * 60 * 1000,
  });

  const createMutation = useMutation({
    mutationFn: createPersona,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["personas"] });
      setShowCreate(false);
      setForm({ name: "", description: "", system_prompt: "", avatar_url: "", network: "" });
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
    if (!form.name.trim()) { setFormErr(t("nameRequired")); return; }
    if (!form.system_prompt.trim()) { setFormErr(t("systemPromptRequired")); return; }
    setFormErr("");
    createMutation.mutate({ ...form, network: form.network || null });
  };

  const systemPersonas = personas.filter((p) => p.is_public && !p.is_own);
  const myPersonas = personas.filter((p) => p.is_own);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-[24px] font-bold text-[#1A1A1A] dark:text-[#EDE8E3]">
            {t("title")}
          </h1>
          <p className="mt-1 text-[16px] text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.45)]">
            {t("subtitle")}
          </p>
        </div>
        {user && (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 rounded-[10px] px-4 py-2 text-[15px] font-semibold text-white transition-all hover:opacity-90"
            style={{ background: "var(--surface-inverse)" }}
          >
            <Plus size={14} />
            {t("createPersona")}
          </button>
        )}
      </div>

      {isLoading && (
        <div className="text-center py-12 text-[rgba(13,13,13,0.40)]">{t("loading")}</div>
      )}

      {/* System personas */}
      {systemPersonas.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-[15px] font-semibold uppercase tracking-wide text-[rgba(13,13,13,0.42)] dark:text-[rgba(236,236,236,0.40)]">
            {t("systemPersonasTitle")}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {systemPersonas.map((p) => (
              <PersonaCard key={p.id} persona={p} canChat={!!user} networks={textNetworks} />
            ))}
          </div>
        </section>
      )}

      {/* My personas */}
      {user && (
        <section>
          <h2 className="mb-3 text-[15px] font-semibold uppercase tracking-wide text-[rgba(13,13,13,0.42)] dark:text-[rgba(236,236,236,0.40)]">
            {t("myPersonasTitle")}
          </h2>
          {myPersonas.length === 0 ? (
            <div className="rounded-[12px] border border-dashed border-[rgba(13,13,13,0.15)] px-6 py-8 text-center dark:border-[rgba(255,255,255,0.10)]">
              <Bot size={28} className="mx-auto mb-2 text-[rgba(13,13,13,0.25)] dark:text-[rgba(236,236,236,0.25)]" />
              <p className="text-[15px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.40)]">
                {t("emptyMyPersonas")}
              </p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {myPersonas.map((p) => (
                <PersonaCard
                  key={p.id}
                  persona={p}
                  canChat={!!user}
                  networks={textNetworks}
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
              {t("newPersonaTitle")}
            </h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="mb-1 block text-[14px] font-medium text-[rgba(13,13,13,0.60)]">
                  {t("nameLabel")}
                </label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder={t("namePlaceholder")}
                  className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-transparent px-3 py-2 text-[15px] outline-none focus:border-[#D97757]"
                />
              </div>
              <div>
                <label className="mb-1 block text-[14px] font-medium text-[rgba(13,13,13,0.60)]">
                  {t("descriptionLabel")}
                </label>
                <input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder={t("descriptionPlaceholder")}
                  className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-transparent px-3 py-2 text-[15px] outline-none focus:border-[#D97757]"
                />
              </div>
              <div>
                <label className="mb-1 block text-[14px] font-medium text-[rgba(13,13,13,0.60)]">
                  {t("systemPromptLabel")}
                </label>
                <textarea
                  value={form.system_prompt}
                  onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                  rows={5}
                  placeholder={t("systemPromptPlaceholder")}
                  className="w-full resize-none rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-transparent px-3 py-2 text-[15px] outline-none focus:border-[#D97757]"
                />
              </div>
              <div>
                <label className="mb-1 block text-[14px] font-medium text-[rgba(13,13,13,0.60)]">
                  {t("defaultModelLabel")}
                </label>
                <select
                  value={form.network}
                  onChange={(e) => setForm({ ...form, network: e.target.value })}
                  className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-transparent px-3 py-2 text-[15px] outline-none focus:border-[#D97757]"
                >
                  <option value="">{t("askAtChatStart")}</option>
                  {textNetworks.map((n) => (
                    <option key={n.slug} value={n.slug}>
                      {t("modelOptionCost", { name: n.name, cost: formatMoney(n.cost_kopecks) })}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.40)]">
                  {t("modelChangeHint")}
                </p>
              </div>
              {formErr && (
                <p className="text-[14px] text-[#e74c3c]">{formErr}</p>
              )}
              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="rounded-[8px] border border-[rgba(13,13,13,0.15)] px-4 py-2 text-[15px] text-[rgba(13,13,13,0.60)] hover:bg-[rgba(13,13,13,0.04)]"
                >
                  {t("cancel")}
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="rounded-[8px] px-4 py-2 text-[15px] font-semibold text-white transition-opacity disabled:opacity-60"
                  style={{ background: "var(--surface-inverse)" }}
                >
                  {createMutation.isPending ? t("creating") : t("create")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function PersonaCard({
  persona,
  canChat,
  networks,
  onDelete,
}: {
  persona: Persona;
  canChat: boolean;
  networks: NetworkListItem[];
  onDelete?: () => void;
}) {
  const t = useTranslations("personas");
  const router = useRouter();
  const [composing, setComposing] = useState(false);
  const [msg, setMsg] = useState("");
  const [networkSlug, setNetworkSlug] = useState("");

  // Предвыбор: модель персоны, иначе первая из каталога
  const effectiveSlug = networkSlug || persona.chat_network_slug || networks[0]?.slug || "";

  const startMutation = useMutation({
    mutationFn: (message: string) =>
      createChat({
        network_slug: effectiveSlug,
        message,
        settings: { system_prompt: persona.system_prompt, persona_id: persona.id },
      }),
    onSuccess: (res) => router.push(`/chat/${res.chat_id}`),
  });

  const canStart = !!effectiveSlug;

  const handleStart = (e: React.FormEvent) => {
    e.preventDefault();
    const text = msg.trim();
    if (!text || startMutation.isPending) return;
    startMutation.mutate(text);
  };

  return (
    <div
      className="group relative flex flex-col gap-2 rounded-[12px] border p-4 transition-shadow hover:shadow-md"
      style={{
        background: "var(--surface, #fff)",
        borderColor: "var(--border-secondary)",
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
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-[rgba(217,119,87,0.10)] text-[#D97757]">
            <Bot size={18} />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-[16px] text-[#1A1A1A] dark:text-[#EDE8E3]">
            {persona.name}
          </p>
          {persona.description && (
            <p className="mt-0.5 text-[14px] text-[rgba(13,13,13,0.52)] dark:text-[rgba(236,236,236,0.45)] line-clamp-2">
              {persona.description}
            </p>
          )}
        </div>
      </div>

      <p className="line-clamp-3 text-[13px] leading-relaxed text-[rgba(13,13,13,0.42)] dark:text-[rgba(236,236,236,0.38)] font-mono border-t border-[rgba(13,13,13,0.06)] pt-2 mt-1">
        {persona.system_prompt}
      </p>

      {persona.network_name && (
        <span className="inline-flex w-fit items-center gap-1.5 rounded-[6px] bg-[rgba(13,13,13,0.05)] px-2 py-1 text-[12px] font-medium text-[rgba(13,13,13,0.55)] dark:bg-[rgba(255,255,255,0.08)] dark:text-[rgba(236,236,236,0.55)]">
          <Cpu size={12} />
          {persona.network_name}
        </span>
      )}

      {/* Start chat */}
      {composing ? (
        <form onSubmit={handleStart} className="mt-1 flex flex-col gap-2">
          {networks.length > 0 && (
            <select
              value={effectiveSlug}
              onChange={(e) => setNetworkSlug(e.target.value)}
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-transparent px-3 py-2 text-[14px] outline-none focus:border-[#D97757]"
            >
              {networks.map((n) => (
                <option key={n.slug} value={n.slug}>
                  {t("modelOptionCost", { name: n.name, cost: formatMoney(n.cost_kopecks) })}
                </option>
              ))}
            </select>
          )}
          <textarea
            autoFocus
            value={msg}
            onChange={(e) => setMsg(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) handleStart(e);
            }}
            rows={2}
            placeholder={t("firstMessagePlaceholder")}
            className="w-full resize-none rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-transparent px-3 py-2 text-[14px] outline-none focus:border-[#D97757]"
          />
          {startMutation.isError && (
            <p className="text-[13px] text-[#e74c3c]">
              {t("startChatError")}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setComposing(false)}
              className="rounded-[8px] px-3 py-1.5 text-[14px] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.04)]"
            >
              {t("cancel")}
            </button>
            <button
              type="submit"
              disabled={!msg.trim() || startMutation.isPending}
              className="flex items-center gap-1.5 rounded-[8px] px-3 py-1.5 text-[14px] font-semibold text-white transition-opacity disabled:opacity-60"
              style={{ background: "var(--surface-inverse)" }}
            >
              {startMutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Send size={14} />
              )}
              {t("send")}
            </button>
          </div>
        </form>
      ) : canChat ? (
        <button
          onClick={() => setComposing(true)}
          disabled={!canStart}
          title={canStart ? undefined : t("noModelAvailable")}
          className="mt-1 flex items-center justify-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 py-2 text-[14px] font-medium text-[rgba(13,13,13,0.70)] transition-colors hover:border-[#D97757] hover:text-[#D97757] disabled:cursor-not-allowed disabled:opacity-50 dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.70)]"
        >
          <MessageSquarePlus size={15} />
          {t("startChat")}
        </button>
      ) : (
        <Link
          href="/login/?next=/personas/"
          className="mt-1 flex items-center justify-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 py-2 text-[14px] font-medium text-[rgba(13,13,13,0.70)] transition-colors hover:border-[#D97757] hover:text-[#D97757] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.70)]"
        >
          <MessageSquarePlus size={15} />
          {t("loginToChat")}
        </Link>
      )}

      {onDelete && (
        <button
          onClick={onDelete}
          className="absolute right-3 top-3 hidden h-7 w-7 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.35)] transition-colors hover:bg-[rgba(231,76,60,0.08)] hover:text-[#e74c3c] group-hover:flex"
          title={t("deletePersona")}
        >
          <Trash2 size={13} />
        </button>
      )}
    </div>
  );
}
