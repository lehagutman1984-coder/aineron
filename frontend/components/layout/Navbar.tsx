"use client";

import Link from "next/link";
import { Star, User, Menu, X, Sun, Moon, Monitor } from "lucide-react";
import { useState } from "react";
import { useAuthStore } from "@/lib/stores/auth";
import { useUIStore, type Theme } from "@/lib/stores/ui";
import { authLogout } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const THEME_CYCLE: Theme[] = ["system", "light", "dark"];

function ThemeIcon({ theme }: { theme: Theme }) {
  if (theme === "dark") return <Moon size={15} />;
  if (theme === "light") return <Sun size={15} />;
  return <Monitor size={15} />;
}

export function Navbar() {
  const { user, stars, logout } = useAuthStore();
  const { theme, setTheme } = useUIStore();
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

  const cycleTheme = () => {
    const idx = THEME_CYCLE.indexOf(theme);
    setTheme(THEME_CYCLE[(idx + 1) % THEME_CYCLE.length]);
  };

  return (
    <header className="sticky top-0 z-50 border-b border-[rgba(13,13,13,0.10)] bg-white/90 backdrop-blur-sm dark:border-[rgba(255,255,255,0.08)] dark:bg-[#1C1917]/90">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 font-semibold text-[15px] text-[#1A1A1A] dark:text-[#EDE8E3]">
          aineron.ru
        </Link>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-1 md:flex">
          <NavLink href="/models/">Каталог</NavLink>
          <NavLink href="/compare/">Сравнение</NavLink>
          <NavLink href="/blog/">Блог</NavLink>
          <NavLink href="/api-docs/">API</NavLink>
          <NavLink href="/ide/">IDE</NavLink>
        </nav>

        {/* Desktop auth + theme toggle */}
        <div className="hidden items-center gap-2 md:flex">
          {/* Theme toggle */}
          <button
            onClick={cycleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-[8px] text-[rgba(13,13,13,0.55)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.50)] dark:hover:bg-[rgba(255,255,255,0.07)] dark:hover:text-[#EDE8E3]"
            title={theme === "system" ? "Системная тема" : theme === "light" ? "Светлая тема" : "Тёмная тема"}
          >
            <ThemeIcon theme={theme} />
          </button>

          {user ? (
            <>
              <div className="flex items-center gap-1.5 rounded-full border border-[rgba(13,13,13,0.12)] px-3 py-1.5 text-[13px] text-[#1A1A1A] dark:border-[rgba(255,255,255,0.12)] dark:text-[#EDE8E3]">
                <Star size={13} className="text-[#D97757]" />
                <span className="font-medium">{stars}</span>
              </div>
              <Link
                href="/account/"
                className="flex items-center gap-1.5 rounded-[8px] px-3 py-1.5 text-[13px] text-[rgba(13,13,13,0.7)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.65)] dark:hover:bg-[rgba(255,255,255,0.07)] dark:hover:text-[#EDE8E3]"
              >
                <User size={15} />
                Кабинет
              </Link>
              <button
                onClick={handleLogout}
                className="px-2 py-1.5 text-[13px] text-[rgba(13,13,13,0.5)] transition-colors hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.4)] dark:hover:text-[#EDE8E3]"
              >
                Выйти
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login/"
                className="rounded-[8px] px-3 py-1.5 text-[13px] text-[rgba(13,13,13,0.7)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.65)] dark:hover:bg-[rgba(255,255,255,0.07)] dark:hover:text-[#EDE8E3]"
              >
                Войти
              </Link>
              <Link
                href="/register/"
                className="rounded-[8px] bg-[#D97757] px-3 py-1.5 text-[13px] font-medium text-white transition-colors hover:bg-[#C4623E]"
              >
                Начать бесплатно
              </Link>
            </>
          )}
        </div>

        {/* Mobile: theme toggle + hamburger */}
        <div className="flex items-center gap-1 md:hidden">
          <button
            onClick={cycleTheme}
            className="flex h-9 w-9 items-center justify-center rounded-[8px] text-[rgba(13,13,13,0.55)] transition-colors hover:bg-[rgba(13,13,13,0.06)] dark:text-[rgba(236,236,236,0.50)] dark:hover:bg-[rgba(255,255,255,0.07)]"
          >
            <ThemeIcon theme={theme} />
          </button>
          <button
            className="flex items-center justify-center rounded-[8px] p-2 text-[rgba(13,13,13,0.7)] transition-colors hover:bg-[rgba(13,13,13,0.06)] dark:text-[rgba(236,236,236,0.65)] dark:hover:bg-[rgba(255,255,255,0.07)]"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="Меню"
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="border-t border-[rgba(13,13,13,0.10)] bg-white px-4 py-3 dark:border-[rgba(255,255,255,0.08)] dark:bg-[#1C1917] md:hidden">
          <div className="flex flex-col gap-1">
            <MobileNavLink href="/models/" onClick={() => setMobileOpen(false)}>Каталог</MobileNavLink>
            <MobileNavLink href="/compare/" onClick={() => setMobileOpen(false)}>Сравнение</MobileNavLink>
            <MobileNavLink href="/blog/" onClick={() => setMobileOpen(false)}>Блог</MobileNavLink>
            <MobileNavLink href="/api-docs/" onClick={() => setMobileOpen(false)}>API</MobileNavLink>
            <MobileNavLink href="/ide/" onClick={() => setMobileOpen(false)}>IDE</MobileNavLink>
            <div className="my-2 border-t border-[rgba(13,13,13,0.08)] dark:border-[rgba(255,255,255,0.06)]" />
            {user ? (
              <>
                <div className="flex items-center gap-2 py-2 text-[13px] text-[rgba(13,13,13,0.7)] dark:text-[rgba(236,236,236,0.6)]">
                  <Star size={13} className="text-[#D97757]" />
                  <span>{stars} звёзд</span>
                </div>
                <MobileNavLink href="/account/" onClick={() => setMobileOpen(false)}>Личный кабинет</MobileNavLink>
                <button
                  onClick={() => { setMobileOpen(false); handleLogout(); }}
                  className="py-2 text-left text-[14px] text-[rgba(13,13,13,0.6)] dark:text-[rgba(236,236,236,0.5)]"
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
                  className="mt-1 block rounded-[8px] bg-[#D97757] px-3 py-2 text-center text-[14px] font-medium text-white"
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
      className="rounded-[8px] px-3 py-1.5 text-[13px] text-[rgba(13,13,13,0.7)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.65)] dark:hover:bg-[rgba(255,255,255,0.07)] dark:hover:text-[#EDE8E3]"
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
      className="py-2 text-[14px] text-[rgba(13,13,13,0.8)] transition-colors hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.75)] dark:hover:text-[#EDE8E3]"
    >
      {children}
    </Link>
  );
}
