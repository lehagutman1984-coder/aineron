import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SpinnerProps {
  size?: number;
  className?: string;
}

export function Spinner({ size = 20, className }: SpinnerProps) {
  return (
    <Loader2
      size={size}
      className={cn("animate-spin text-[#0a7cff]", className)}
    />
  );
}

export function FullPageSpinner() {
  return (
    <div className="flex h-full min-h-[200px] w-full items-center justify-center">
      <Spinner size={32} />
    </div>
  );
}
