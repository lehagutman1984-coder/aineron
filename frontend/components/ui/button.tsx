import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";
export type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children: ReactNode;
}

const BASE =
  "inline-flex items-center justify-center gap-2 font-medium rounded-[8px] transition-all duration-150 cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D97757] disabled:opacity-50 disabled:pointer-events-none";

const VARIANTS: Record<ButtonVariant, string> = {
  primary:     "bg-[#D97757] text-white hover:bg-[#C4623E] active:bg-[#0055aa]",
  secondary:   "bg-[rgba(13,13,13,0.06)] text-[#1A1A1A] hover:bg-[rgba(13,13,13,0.10)] border border-[rgba(13,13,13,0.12)]",
  ghost:       "text-[rgba(13,13,13,0.58)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A]",
  destructive: "bg-[#e74c3c] text-white hover:bg-[#c0392b] active:bg-[#a93226]",
};

const SIZES: Record<ButtonSize, string> = {
  sm: "h-8  px-3 text-[15px]",
  md: "h-10 px-4 text-[16px]",
  lg: "h-12 px-6 text-[17px]",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(BASE, VARIANTS[variant], SIZES[size], className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 size={16} className="animate-spin" />}
      {children}
    </button>
  );
}
