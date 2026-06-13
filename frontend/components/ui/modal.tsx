"use client";

import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const SIZES = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-2xl",
};

export function Modal({
  open,
  onClose,
  title,
  children,
  size = "md",
  className,
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />

      {/* Panel */}
      <div
        className={cn(
          "relative w-full rounded-[16px] bg-white p-6 shadow-[0_8px_32px_rgba(0,0,0,0.14)]",
          SIZES[size],
          className
        )}
        role="dialog"
        aria-modal
      >
        {title && (
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-[18px] font-600 text-[#0d0d0d]">{title}</h2>
            <button
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.4)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] transition-all"
            >
              <X size={18} />
            </button>
          </div>
        )}
        {!title && (
          <button
            onClick={onClose}
            className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.4)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] transition-all"
          >
            <X size={18} />
          </button>
        )}
        {children}
      </div>
    </div>
  );
}
