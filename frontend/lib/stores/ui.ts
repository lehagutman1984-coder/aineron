import { create } from "zustand";

type ModalKey = "auth" | "tariffs" | "stars" | null;

interface UIState {
  openModal: ModalKey;
  toasts: Toast[];

  showModal: (key: NonNullable<ModalKey>) => void;
  hideModal: () => void;
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

interface Toast {
  id: string;
  message: string;
  type: "success" | "error" | "info";
  duration?: number;
}

let toastSeq = 0;

export const useUIStore = create<UIState>((set) => ({
  openModal: null,
  toasts: [],

  showModal: (key) => set({ openModal: key }),
  hideModal: () => set({ openModal: null }),

  addToast: (toast) => {
    const id = `toast-${++toastSeq}`;
    const duration = toast.duration ?? 4000;

    set((state) => ({
      toasts: [...state.toasts, { ...toast, id }],
    }));

    setTimeout(() => {
      set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      }));
    }, duration);
  },

  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}));
