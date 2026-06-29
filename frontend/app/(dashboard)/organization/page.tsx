"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Building2, Users, Plus, Trash2, Mail, ArrowLeft,
  FileText, Check, X, ChevronRight, Send, Copy, RefreshCw,
} from "lucide-react";
import {
  listOrgs, createOrg, listOrgMembers, removeOrgMember,
  listOrgInvites, createOrgInvite,
  listInvoices, createInvoice,
  generateOrgTgToken, listOrgTgGroups, unregisterOrgTgGroup,
} from "@/lib/api/client";
import { APIError } from "@/lib/api/client";
import type { Organization, OrgMember, OrgInvite, Invoice } from "@/lib/api/types";

export default function OrganizationPage() {
  const qc = useQueryClient();
  const [selectedOrgId, setSelectedOrgId] = useState<number | null>(null);
  const [createOrgOpen, setCreateOrgOpen] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [orgInn, setOrgInn] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const { data: orgs = [], isLoading } = useQuery<Organization[]>({
    queryKey: ["orgs"],
    queryFn: listOrgs,
  });

  const createOrgMutation = useMutation({
    mutationFn: () => createOrg({ name: orgName.trim(), inn: orgInn.trim() }),
    onSuccess: (org) => {
      qc.invalidateQueries({ queryKey: ["orgs"] });
      setOrgName("");
      setOrgInn("");
      setCreateOrgOpen(false);
      setSelectedOrgId(org.id);
    },
    onError: (err) => {
      setCreateError(err instanceof APIError ? err.message : "Ошибка создания");
    },
  });

  const selectedOrg = orgs.find((o) => o.id === selectedOrgId) ?? null;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="mb-8 flex items-center gap-3">
        <Link
          href="/account/"
          className="flex items-center gap-1 text-[13px] text-[rgba(13,13,13,0.5)] hover:text-[#1A1A1A] transition-colors"
        >
          <ArrowLeft size={14} />
          Кабинет
        </Link>
        <span className="text-[rgba(13,13,13,0.25)]">/</span>
        <h1 className="text-[20px] font-bold text-[#1A1A1A]">Организации</h1>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[280px_1fr]">
        {/* Sidebar: org list */}
        <aside>
          <div className="mb-3 flex items-center justify-between">
            <p className="text-[12px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
              Ваши организации
            </p>
            <button
              onClick={() => setCreateOrgOpen((v) => !v)}
              className="flex h-6 w-6 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.5)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] transition-all"
            >
              <Plus size={14} />
            </button>
          </div>

          {createOrgOpen && (
            <form
              onSubmit={(e) => { e.preventDefault(); setCreateError(null); createOrgMutation.mutate(); }}
              className="mb-3 flex flex-col gap-2 rounded-[10px] border border-[rgba(13,13,13,0.12)] bg-white p-3"
            >
              <input
                type="text"
                placeholder="Название организации"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                required
                autoFocus
                className="w-full rounded-[6px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[13px] outline-none focus:border-[#D97757] focus:ring-1 focus:ring-[rgba(217,119,87,0.15)]"
              />
              <input
                type="text"
                placeholder="ИНН (необязательно)"
                value={orgInn}
                onChange={(e) => setOrgInn(e.target.value)}
                maxLength={12}
                className="w-full rounded-[6px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[13px] outline-none focus:border-[#D97757] focus:ring-1 focus:ring-[rgba(217,119,87,0.15)]"
              />
              {createError && (
                <p className="text-[12px] text-[#e74c3c]">{createError}</p>
              )}
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={!orgName.trim() || createOrgMutation.isPending}
                  className="flex-1 h-8 rounded-[6px] bg-[#D97757] text-[12px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors"
                >
                  {createOrgMutation.isPending ? "..." : "Создать"}
                </button>
                <button
                  type="button"
                  onClick={() => setCreateOrgOpen(false)}
                  className="h-8 w-8 flex items-center justify-center rounded-[6px] border border-[rgba(13,13,13,0.15)] text-[rgba(13,13,13,0.5)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
                >
                  <X size={13} />
                </button>
              </div>
            </form>
          )}

          {isLoading ? (
            <div className="py-6 text-center text-[13px] text-[rgba(13,13,13,0.45)]">
              Загрузка...
            </div>
          ) : orgs.length === 0 ? (
            <div className="rounded-[10px] border border-dashed border-[rgba(13,13,13,0.18)] py-8 text-center">
              <Building2 size={24} className="mx-auto mb-2 text-[rgba(13,13,13,0.25)]" />
              <p className="text-[13px] text-[rgba(13,13,13,0.5)]">Нет организаций</p>
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              {orgs.map((org) => (
                <button
                  key={org.id}
                  onClick={() => setSelectedOrgId(org.id)}
                  className={[
                    "flex w-full items-center gap-2 rounded-[8px] px-3 py-2.5 text-left transition-all",
                    selectedOrgId === org.id
                      ? "bg-[rgba(217,119,87,0.08)] text-[#D97757]"
                      : "text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.05)] hover:text-[#1A1A1A]",
                  ].join(" ")}
                >
                  <Building2 size={14} className="shrink-0" />
                  <span className="flex-1 truncate text-[13px] font-medium">
                    {org.name}
                  </span>
                  <ChevronRight size={13} className="shrink-0 opacity-40" />
                </button>
              ))}
            </div>
          )}
        </aside>

        {/* Main: org detail */}
        <main>
          {!selectedOrg ? (
            <div className="flex h-64 items-center justify-center rounded-[14px] border border-dashed border-[rgba(13,13,13,0.15)] text-[14px] text-[rgba(13,13,13,0.4)]">
              Выберите организацию
            </div>
          ) : (
            <OrgDetail org={selectedOrg} />
          )}
        </main>
      </div>
    </div>
  );
}

function OrgDetail({ org }: { org: Organization }) {
  const qc = useQueryClient();
  const isAdmin = org.user_role === "owner" || org.user_role === "admin";

  const { data: members = [] } = useQuery<OrgMember[]>({
    queryKey: ["org-members", org.id],
    queryFn: () => listOrgMembers(org.id),
  });

  const { data: invites = [] } = useQuery<OrgInvite[]>({
    queryKey: ["org-invites", org.id],
    queryFn: () => listOrgInvites(org.id),
    enabled: isAdmin,
  });

  const { data: invoices = [] } = useQuery<Invoice[]>({
    queryKey: ["org-invoices", org.id],
    queryFn: () => listInvoices(org.id),
    enabled: isAdmin,
  });

  const removeMember = useMutation({
    mutationFn: (userId: number) => removeOrgMember(org.id, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["org-members", org.id] }),
  });

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const inviteMutation = useMutation({
    mutationFn: () => createOrgInvite(org.id, inviteEmail.trim().toLowerCase()),
    onSuccess: () => {
      setInviteEmail("");
      setInviteError(null);
      qc.invalidateQueries({ queryKey: ["org-invites", org.id] });
    },
    onError: (err) => {
      setInviteError(err instanceof APIError ? err.message : "Ошибка");
    },
  });

  const [invoiceAmount, setInvoiceAmount] = useState("");
  const [invoiceError, setInvoiceError] = useState<string | null>(null);
  const invoiceMutation = useMutation({
    mutationFn: () =>
      createInvoice(org.id, { amount_rub: Number(invoiceAmount) }),
    onSuccess: () => {
      setInvoiceAmount("");
      setInvoiceError(null);
      qc.invalidateQueries({ queryKey: ["org-invoices", org.id] });
    },
    onError: (err) => {
      setInvoiceError(err instanceof APIError ? err.message : "Ошибка");
    },
  });

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-5">
        <div className="mb-1 flex items-center gap-2">
          <Building2 size={18} className="text-[#D97757]" />
          <h2 className="text-[17px] font-bold text-[#1A1A1A]">{org.name}</h2>
          <span className="rounded-full bg-[rgba(13,13,13,0.07)] px-2 py-0.5 text-[11px] text-[rgba(13,13,13,0.55)]">
            {org.user_role}
          </span>
        </div>
        {org.inn && (
          <p className="text-[13px] text-[rgba(13,13,13,0.55)]">ИНН: {org.inn}</p>
        )}
        <div className="mt-3 flex items-center gap-4">
          <div className="text-center">
            <p className="text-[20px] font-bold text-[#1A1A1A]">
              {Number(org.balance_rub).toFixed(2)}
            </p>
            <p className="text-[11px] text-[rgba(13,13,13,0.5)]">руб. баланс</p>
          </div>
          <div className="text-center">
            <p className="text-[20px] font-bold text-[#1A1A1A]">{org.member_count}</p>
            <p className="text-[11px] text-[rgba(13,13,13,0.5)]">участников</p>
          </div>
        </div>
      </div>

      {/* Members */}
      <Section title="Участники" icon={<Users size={14} />}>
        <div className="flex flex-col gap-1.5">
          {members.map((m) => (
            <div
              key={m.id}
              className="flex items-center gap-3 rounded-[8px] border border-[rgba(13,13,13,0.10)] bg-white px-3.5 py-2.5"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[rgba(217,119,87,0.10)] text-[11px] font-semibold text-[#D97757]">
                {m.email[0].toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="truncate text-[13px] font-medium text-[#1A1A1A]">{m.email}</p>
                <p className="text-[11px] text-[rgba(13,13,13,0.45)]">{m.role}</p>
              </div>
              {isAdmin && m.role !== "owner" && (
                <button
                  onClick={() => removeMember.mutate(m.user_id)}
                  className="flex h-6 w-6 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.35)] hover:bg-[rgba(231,76,60,0.08)] hover:text-[#e74c3c] transition-all"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          ))}
        </div>
        {isAdmin && (
          <form
            onSubmit={(e) => { e.preventDefault(); inviteMutation.mutate(); }}
            className="mt-3 flex items-center gap-2"
          >
            <input
              type="email"
              placeholder="email участника"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              required
              className="flex-1 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[13px] outline-none focus:border-[#D97757] focus:ring-1 focus:ring-[rgba(217,119,87,0.15)]"
            />
            <button
              type="submit"
              disabled={inviteMutation.isPending}
              className="flex h-9 items-center gap-1.5 rounded-[8px] bg-[#D97757] px-3 text-[13px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors"
            >
              <Mail size={13} />
              Пригласить
            </button>
          </form>
        )}
        {inviteError && (
          <p className="mt-1.5 text-[12px] text-[#e74c3c]">{inviteError}</p>
        )}
        {invites.length > 0 && (
          <div className="mt-3 flex flex-col gap-1">
            <p className="text-[11px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.4)]">
              Ожидают принятия
            </p>
            {invites.map((inv) => (
              <div
                key={inv.id}
                className="flex items-center gap-2 rounded-[6px] bg-[rgba(13,13,13,0.03)] px-3 py-1.5 text-[12px] text-[rgba(13,13,13,0.6)]"
              >
                <Mail size={11} />
                {inv.email}
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Invoices */}
      {isAdmin && (
        <Section title="Счета на оплату" icon={<FileText size={14} />}>
          <div className="flex flex-col gap-1.5">
            {invoices.length === 0 ? (
              <p className="text-[13px] text-[rgba(13,13,13,0.45)]">Счетов нет</p>
            ) : (
              invoices.map((inv) => (
                <div
                  key={inv.id}
                  className="flex items-center gap-3 rounded-[8px] border border-[rgba(13,13,13,0.10)] bg-white px-3.5 py-2.5"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-medium text-[#1A1A1A]">
                      {inv.number}
                    </p>
                    <p className="text-[11px] text-[rgba(13,13,13,0.5)]">
                      {inv.description}
                    </p>
                  </div>
                  <p className="shrink-0 text-[13px] font-semibold text-[#1A1A1A]">
                    {Number(inv.amount_rub).toLocaleString("ru-RU")} руб.
                  </p>
                  <StatusBadge status={inv.status} />
                </div>
              ))
            )}
          </div>
          <form
            onSubmit={(e) => { e.preventDefault(); invoiceMutation.mutate(); }}
            className="mt-3 flex items-center gap-2"
          >
            <input
              type="number"
              placeholder="Сумма в рублях"
              value={invoiceAmount}
              onChange={(e) => setInvoiceAmount(e.target.value)}
              min="100"
              step="100"
              required
              className="flex-1 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[13px] outline-none focus:border-[#D97757] focus:ring-1 focus:ring-[rgba(217,119,87,0.15)]"
            />
            <button
              type="submit"
              disabled={invoiceMutation.isPending}
              className="h-9 rounded-[8px] bg-[#D97757] px-3 text-[13px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors"
            >
              Выставить счёт
            </button>
          </form>
          {invoiceError && (
            <p className="mt-1.5 text-[12px] text-[#e74c3c]">{invoiceError}</p>
          )}
        </Section>
      )}

      {/* ── Telegram Integration ────────────────────────────────── */}
      <TelegramSection orgId={org.id} />
    </div>
  );
}

function TelegramSection({ orgId }: { orgId: number }) {
  const qc = useQueryClient();
  const [token, setToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: groups = [] } = useQuery({
    queryKey: ["org-tg-groups", orgId],
    queryFn: () => listOrgTgGroups(orgId),
    staleTime: 30_000,
  });

  const genTokenMutation = useMutation({
    mutationFn: () => generateOrgTgToken(orgId),
    onSuccess: (res) => setToken(res.token),
  });

  const unregisterMutation = useMutation({
    mutationFn: (groupId: number) => unregisterOrgTgGroup(orgId, groupId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["org-tg-groups", orgId] }),
  });

  const handleCopy = () => {
    if (!token) return;
    navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Section title="Telegram-интеграция" icon={<Send size={14} />}>
      <p className="mb-4 text-[13px] text-[rgba(13,13,13,0.55)]">
        Подключи Telegram-группы к организации. Участники смогут использовать бота за счёт баланса организации.
      </p>

      {/* Token generator */}
      <div className="mb-4 rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
        <p className="mb-2 text-[12px] font-medium text-[rgba(13,13,13,0.55)]">Токен подключения</p>
        {token ? (
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded-[6px] bg-[rgba(13,13,13,0.05)] px-3 py-1.5 text-[13px] font-mono text-[#1A1A1A] overflow-auto">
              {token}
            </code>
            <button onClick={handleCopy} className="flex h-8 w-8 items-center justify-center rounded-[7px] border border-[rgba(13,13,13,0.12)] hover:bg-[rgba(13,13,13,0.05)] transition-colors">
              {copied ? <Check size={13} className="text-[#22a85a]" /> : <Copy size={13} />}
            </button>
          </div>
        ) : (
          <p className="text-[12px] text-[rgba(13,13,13,0.40)]">Нет активного токена</p>
        )}
        <div className="mt-3 flex items-start gap-3">
          <button
            onClick={() => genTokenMutation.mutate()}
            disabled={genTokenMutation.isPending}
            className="flex items-center gap-1.5 rounded-[8px] bg-[#D97757] px-3 py-1.5 text-[12px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors"
          >
            <RefreshCw size={12} className={genTokenMutation.isPending ? "animate-spin" : ""} />
            {token ? "Обновить токен" : "Создать токен"}
          </button>
          {token && (
            <div className="text-[11px] text-[rgba(13,13,13,0.45)] leading-relaxed">
              Добавь бота в группу, дай права <b>администратора</b> и напиши:<br />
              <code className="font-mono">/reggroup {token}</code>
            </div>
          )}
        </div>
      </div>

      {/* Connected groups */}
      {groups.length > 0 && (
        <div>
          <p className="mb-2 text-[12px] font-medium text-[rgba(13,13,13,0.55)]">Подключённые группы ({groups.length})</p>
          <div className="flex flex-col gap-2">
            {groups.map((g) => (
              <div key={g.id} className="flex items-center justify-between rounded-[8px] border border-[rgba(13,13,13,0.08)] bg-white px-3 py-2">
                <div>
                  <p className="text-[13px] font-medium text-[#1A1A1A]">{g.group_title || `Group ${g.group_id}`}</p>
                  <p className="text-[11px] text-[rgba(13,13,13,0.40)]">ID: {g.group_id}</p>
                </div>
                <button
                  onClick={() => unregisterMutation.mutate(g.group_id)}
                  className="flex h-7 w-7 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.35)] hover:bg-[rgba(231,76,60,0.09)] hover:text-[#e74c3c] transition-colors"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </Section>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.02)] p-5">
      <div className="mb-4 flex items-center gap-2 text-[12px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.5)]">
        <span className="text-[#D97757]">{icon}</span>
        {title}
      </div>
      {children}
    </div>
  );
}

function StatusBadge({ status }: { status: "pending" | "paid" | "cancelled" }) {
  const map = {
    pending: "text-[#d4ac0d] bg-[rgba(241,196,15,0.10)]",
    paid: "text-[#1abc9c] bg-[rgba(26,188,156,0.10)]",
    cancelled: "text-[rgba(13,13,13,0.5)] bg-[rgba(13,13,13,0.06)]",
  };
  const label = { pending: "Ожидает", paid: "Оплачен", cancelled: "Отменён" };
  return (
    <span
      className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${map[status]}`}
    >
      {label[status]}
    </span>
  );
}
