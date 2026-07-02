import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AuthUser } from "../api/types";

interface AuthState {
  user: AuthUser | null;
  /** Баланс в копейках (1 звезда legacy = 100 коп.). Источник истины для отображения — см. lib/money.ts formatRub(). */
  balanceKopecks: number;
  isLoading: boolean;

  setUser: (user: AuthUser | null) => void;
  setBalance: (balanceKopecks: number) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      balanceKopecks: 0,
      isLoading: true,

      setUser: (user) =>
        set({
          user,
          balanceKopecks: user?.balance_kopecks ?? 0,
          isLoading: false,
        }),
      setBalance: (balanceKopecks) =>
        set((state) => ({
          balanceKopecks,
          user: state.user
            ? {
                ...state.user,
                balance_kopecks: balanceKopecks,
                pages_count: Math.floor(balanceKopecks / 100),
              }
            : null,
        })),
      setLoading: (isLoading) => set({ isLoading }),
      logout: () => set({ user: null, balanceKopecks: 0, isLoading: false }),
    }),
    {
      name: "aineron-auth",
      version: 2,
      // v1 хранил баланс в звёздах (поле "stars"). Так как эквивалентность
      // 1 звезда = 100 коп. не всегда точна после дробного ценообразования,
      // при миграции сбрасываем локальный кэш баланса — свежее значение
      // придёт с сервера при следующем запросе (AuthInit).
      migrate: (persistedState) => {
        const state = (persistedState as { user?: AuthUser | null }) ?? {};
        return { user: state.user ?? null, balanceKopecks: 0 };
      },
      partialize: (state) => ({ user: state.user, balanceKopecks: state.balanceKopecks }),
    }
  )
);
