import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export function Input({ label, error, hint, className, id, ...props }: InputProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label
          htmlFor={inputId}
          className="text-[13px] font-medium text-[rgba(13,13,13,0.58)]"
        >
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={cn(
          "h-10 w-full rounded-[8px] border border-[rgba(13,13,13,0.12)] bg-white px-3 text-[14px] text-[#0d0d0d] outline-none transition-all",
          "placeholder:text-[rgba(13,13,13,0.35)]",
          "focus:border-[#0a7cff] focus:ring-2 focus:ring-[#0a7cff]/15",
          "disabled:cursor-not-allowed disabled:opacity-50",
          error && "border-[#e74c3c] focus:border-[#e74c3c] focus:ring-[#e74c3c]/15",
          className
        )}
        {...props}
      />
      {error && (
        <p className="text-[12px] text-[#e74c3c]">{error}</p>
      )}
      {hint && !error && (
        <p className="text-[12px] text-[rgba(13,13,13,0.4)]">{hint}</p>
      )}
    </div>
  );
}
