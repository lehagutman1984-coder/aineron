"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard,
  CreditCard,
  Key,
  Users,
  FolderOpen,
  LogOut,
  Star,
  BarChart2,
  MessageCircle,
  AppWindow,
  Heart,
} from "lucide-react";
import { useAuthStore } from "@/lib/stores/auth";
import { authLogout } from "@/lib/api/client";
import { useEffect } from "react";

const NAV = [
  { href: "/account/", label: "Обзор", icon: LayoutDashboard, exact: true },
  { href: "/account/analytics/", label: "Аналитика", icon: BarChart2 },
  { href: "/account/billing/", label: "Тарифы и платежи", icon: CreditCard },
  { href: "/account/keys/", label: "API-ключи", icon: Key },
  { href: "/account/referral/", label: "Партнёрская программа", icon: Users },
  { href: "/account/files/", label: "Мои файлы", icon: FolderOpen },
  { href: "/account/favorites/", label: "Избранное", icon: Heart },
  { href: "/account/telegram/", label: "Telegram", icon: MessageCircle },
  { href: "/account/oauth-apps/", label: "OAuth-приложения", icon: AppWindow },
];

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, stars, isLoading, logout } = useAuthStore();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login/?next=" + encodeURIComponent(pathname));
    }
  }, [isLoading, user, pathname, router]);

  const handleLogout = async () => {
    try { await authLogout(); } catch {}
    logout();
    window.location.href = "/";
  };

  const isActive = (item: (typeof NAV)[number]) =>
    item.exact ? pathname === item.href : pathname.startsWith(item.href);

  return (
    <div className="min-h-[calc(100vh-56px)] bg-[#FAF9F7]">
      {/* Mobile tab bar */}
      <div className="sticky top-14 z-30 border-b border-[rgba(13,13,13,0.10)] bg-white md:hidden">
        <div
          className="flex overflow-x-auto gap-0.5 px-3 py-1.5"
          style={{ scrollbarWidth: "none" }}
        >
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = isActive(item);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex shrink-0 items-center gap-1.5 rounded-[7px] px-3 py-2 text-[12px] font-medium whitespace-nowrap transition-all ${
                  active
                    ? "bg-[rgba(217,119,87,0.08)] text-[#D97757]"
                    : "text-[rgba(13,13,13,0.55)] hover:text-[#1A1A1A]"
                }`}
              >
                <Icon size={13} />
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>

      {/* Desktop */}
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="flex items-start gap-6">
          {/* Sidebar */}
          <aside className="hidden md:flex w-[220px] shrink-0 flex-col gap-3 sticky top-[70px] py-8">
            {/* User card */}
            <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
              <p className="truncate text-[13px] font-semibold text-[#1A1A1A]">
                {user?.email ?? "—"}
              </p>
              <div className="mt-1.5 flex items-center gap-1.5">
                <Star size={12} className="text-[#D97757]" />
                <span className="text-[12px] text-[rgba(13,13,13,0.50)]">
                  {stars ?? 0} звёзд
                </span>
              </div>
            </div>

            {/* Nav */}
            <nav className="overflow-hidden rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white">
              {NAV.map((item) => {
                const Icon = item.icon;
                const active = isActive(item);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 border-b border-[rgba(13,13,13,0.06)] px-4 py-3 text-[13px] last:border-0 transition-colors ${
                      active
                        ? "bg-[rgba(217,119,87,0.06)] font-medium text-[#D97757]"
                        : "text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.03)] hover:text-[#1A1A1A]"
                    }`}
                  >
                    <Icon
                      size={15}
                      className={active ? "text-[#D97757]" : "text-[rgba(13,13,13,0.38)]"}
                    />
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            {/* Logout */}
            <button
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-[10px] px-4 py-2.5 text-[13px] text-[rgba(13,13,13,0.45)] hover:bg-white hover:text-[rgba(13,13,13,0.75)] transition-colors"
            >
              <LogOut size={15} />
              Выйти
            </button>
          </aside>

          {/* Page content — pages control their own padding */}
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </div>
    </div>
  );
}
