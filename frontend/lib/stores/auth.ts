import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "../api/types";

interface AuthState {
  user: User | null;
  stars: number;
  isLoading: boolean;

  setUser: (user: User | null) => void;
  setStars: (stars: number) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      stars: 0,
      isLoading: true,

      setUser: (user) =>
        set({ user, stars: user?.pages_count ?? 0, isLoading: false }),
      setStars: (stars) =>
        set((state) => ({
          stars,
          user: state.user ? { ...state.user, pages_count: stars } : null,
        })),
      setLoading: (isLoading) => set({ isLoading }),
      logout: () => set({ user: null, stars: 0, isLoading: false }),
    }),
    {
      name: "aineron-auth",
      partialize: (state) => ({ user: state.user, stars: state.stars }),
    }
  )
);
