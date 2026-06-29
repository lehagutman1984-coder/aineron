"use client";

import { CheckCircle, XCircle, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/stores/ui";

const ICONS = {
  success: CheckCircle,
  error:   XCircle,
  info:    Info,
};

const COLORS = {
  success: "border-[#1abc9c] bg-[rgba(26,188,156,0.06)]",
  error:   "border-[#e74c3c] bg-[rgba(231,76,60,0.06)]",
  info:    "border-[#f0a38a] bg-[rgba(10,124,255,0.06)]",
};

const ICON_COLORS = {
  success: "text-[#1abc9c]",
  error:   "text-[#e74c3c]",
  info:    "text-[#f0a38a]",
};

export function ToastContainer() {
  const { toasts, removeToast } = useUIStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[2000] flex flex-col gap-2">
      {toasts.map((toast) => {
        const IconComponent = ICONS[toast.type];
        return (
          <div
            key={toast.id}
            className={cn(
              "flex items-start gap-3 min-w-[280px] max-w-[360px] rounded-[10px] border p-4 shadow-[0_4px_12px_rgba(0,0,0,0.10)]",
              COLORS[toast.type]
            )}
          >
            <IconComponent
              size={18}
              className={cn("mt-0.5 shrink-0", ICON_COLORS[toast.type])}
            />
            <p className="flex-1 text-[13px] text-[#0d0d0d] leading-snug">
              {toast.message}
            </p>
            <button
              onClick={() => removeToast(toast.id)}
              className="shrink-0 text-[rgba(13,13,13,0.35)] hover:text-[#0d0d0d] transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
