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
      className="inline-flex items-center gap-1.5 rounded-[8px] bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E]"
    >
      <Wand2 size={14} />
      Попробовать этот промт
    </button>
  );
}
