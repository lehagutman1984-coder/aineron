import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export type BadgeVariant = "default" | "accent" | "success" | "warning" | "destructive" | "outline";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: ReactNode;
}

const VARIANTS: Record<BadgeVariant, string> = {
  default:     "bg-[rgba(13,13,13,0.08)] text-[rgba(13,13,13,0.7)]",
  accent:      "bg-[rgba(217,119,87,0.12)] text-[#D97757]",
  success:     "bg-[rgba(26,188,156,0.12)] text-[#1abc9c]",
  warning:     "bg-[rgba(241,196,15,0.12)] text-[#d4ac0d]",
  destructive: "bg-[rgba(231,76,60,0.12)] text-[#e74c3c]",
  outline:     "border border-[rgba(13,13,13,0.18)] text-[rgba(13,13,13,0.6)]",
};

export function Badge({
  variant = "default",
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[12px] font-500",
        VARIANTS[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}
