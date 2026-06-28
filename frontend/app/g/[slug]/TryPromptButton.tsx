"use client";

import { useRouter } from "next/navigation";
import { Wand2 } from "lucide-react";

const PREFILL_KEY = "aineron_prefill_prompt";

export function TryPromptButton({ prompt }: { prompt: string }) {
  const router = useRouter();
  const onClick = () => {
    try {
      localStorage.setItem(PREFILL_KEY, prompt);
    } catch {}
    router.push("/models/");
  };
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-[8px] bg-[#0a7cff] px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-[#0068e0]"
    >
      <Wand2 size={14} />
      Попробовать этот промт
    </button>
  );
}
