"use client";

import Link from "next/link";
import { Star, User, Menu, X } from "lucide-react";
import { useState } from "react";
import { useAuthStore } from "@/lib/stores/auth";
import { authLogout } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export function Navbar() {
  const { user, stars, logout } = useAuthStore();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await authLogout();
    } catch {
      // ignore
    }
    logout();
    window.location.href = "/";
  };

  return (
    <header className="sticky top-0 z-50 border-b border-[rgba(13,13,13,0.10)] bg-white/90 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 font-semibold text-[15px] text-[#0d0d0d]">
          aineron.ru
        </Link>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-1 md:flex">
          <NavLink href="/models/">Каталог</NavLink>
          <NavLink href="/blog/">Блог</NavLink>
          <NavLink href="/api-docs/">API</NavLink>
          <NavLink href="/ide/">IDE</NavLink>
        </nav>

        {/* Desktop auth */}
        <div className="hidden items-center gap-2 md:flex">
          {user ? (
            <>
              <div className="flex items-center gap-1.5 rounded-full border border-[rgba(13,13,13,0.12)] px-3 py-1.5 text-[13px] text-[#0d0d0d]">
                <Star size={13} className="text-[#0a7cff]" />
                <span className="font-medium">{stars}</span>
              </div>
              <Link
                href="/account/"
                className="flex items-center gap-1.5 rounded-[8px] px-3 py-1.5 text-[13px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] transition-colors"
              >
                <User size={15} />
                Кабинет
              </Link>
              <button
                onClick={handleLogout}
                className="text-[13px] text-[rgba(13,13,13,0.5)] hover:text-[#0d0d0d] px-2 py-1.5 transition-colors"
              >
                Выйти
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login/"
                className="rounded-[8px] px-3 py-1.5 text-[13px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] transition-colors"
              >
                Войти
              </Link>
              <Link
                href="/register/"
                className="rounded-[8px] bg-[#0a7cff] px-3 py-1.5 text-[13px] font-medium text-white hover:bg-[#0066cc] transition-colors"
              >
                Начать бесплатно
              </Link>
            </>
          )}
        </div>

        {/* Mobile toggle */}
        <button
          className="flex items-center justify-center rounded-[8px] p-2 text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.06)] md:hidden"
          onClick={() => setMobileOpen((v) => !v)}
          aria-label="Меню"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="border-t border-[rgba(13,13,13,0.10)] bg-white px-4 py-3 md:hidden">
          <div className="flex flex-col gap-1">
            <MobileNavLink href="/models/" onClick={() => setMobileOpen(false)}>Каталог</MobileNavLink>
            <MobileNavLink href="/blog/" onClick={() => setMobileOpen(false)}>Блог</MobileNavLink>
            <MobileNavLink href="/api-docs/" onClick={() => setMobileOpen(false)}>API</MobileNavLink>
            <MobileNavLink href="/ide/" onClick={() => setMobileOpen(false)}>IDE</MobileNavLink>
            <div className="my-2 border-t border-[rgba(13,13,13,0.08)]" />
            {user ? (
              <>
                <div className="flex items-center gap-2 py-2 text-[13px] text-[rgba(13,13,13,0.7)]">
                  <Star size={13} className="text-[#0a7cff]" />
                  <span>{stars} звёзд</span>
                </div>
                <MobileNavLink href="/account/" onClick={() => setMobileOpen(false)}>Личный кабинет</MobileNavLink>
                <button
                  onClick={() => { setMobileOpen(false); handleLogout(); }}
                  className="py-2 text-left text-[14px] text-[rgba(13,13,13,0.6)]"
                >
                  Выйти
                </button>
              </>
            ) : (
              <>
                <MobileNavLink href="/login/" onClick={() => setMobileOpen(false)}>Войти</MobileNavLink>
                <Link
                  href="/register/"
                  onClick={() => setMobileOpen(false)}
                  className="mt-1 block rounded-[8px] bg-[#0a7cff] px-3 py-2 text-center text-[14px] font-medium text-white"
                >
                  Начать бесплатно
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="rounded-[8px] px-3 py-1.5 text-[13px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] transition-colors"
    >
      {children}
    </Link>
  );
}

function MobileNavLink({
  href,
  onClick,
  children,
}: {
  href: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className="py-2 text-[14px] text-[rgba(13,13,13,0.8)] hover:text-[#0d0d0d] transition-colors"
    >
      {children}
    </Link>
  );
}
