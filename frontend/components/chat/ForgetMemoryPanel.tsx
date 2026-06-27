"use client";

import { useState, useEffect, useRef } from "react";
import { Brain, X, Loader2 } from "lucide-react";
import { getMemoryFacts, deactivateMemoryFact } from "@/lib/api/client";

interface Fact {
  id: number;
  content: string;
  category: string;
  is_active: boolean;
}

interface Props {
  onClose: () => void;
}

export function ForgetMemoryPanel({ onClose }: Props) {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [loading, setLoading] = useState(true);
  const [deactivating, setDeactivating] = useState<Set<number>>(new Set());
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getMemoryFacts().then((f) => {
      setFacts(f.filter((x) => x.is_active).slice(0, 8));
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const handleDeactivate = async (id: number) => {
    setDeactivating((s) => new Set(s).add(id));
    await deactivateMemoryFact(id);
    setFacts((prev) => prev.filter((f) => f.id !== id));
    setDeactivating((s) => { const n = new Set(s); n.delete(id); return n; });
  };

  return (
    <div
      ref={ref}
      className="absolute bottom-full mb-1 right-0 z-50 w-[280px] rounded-[12px] border border-[rgba(13,13,13,0.1)] bg-white shadow-xl dark:bg-[#1a1a1a] dark:border-[rgba(255,255,255,0.1)]"
    >
      <div className="flex items-center gap-2 border-b border-[rgba(13,13,13,0.07)] px-3 py-2.5 dark:border-[rgba(255,255,255,0.07)]">
        <Brain size={13} className="text-[#7c3aed]" />
        <span className="flex-1 text-[12px] font-semibold text-[#0d0d0d] dark:text-[#ececec]">Забыть из памяти</span>
        <button onClick={onClose} className="text-[rgba(13,13,13,0.35)] hover:text-[#0d0d0d]"><X size={12} /></button>
      </div>
      <div className="max-h-[240px] overflow-y-auto px-2 py-1.5">
        {loading && <div className="flex justify-center py-4"><Loader2 size={16} className="animate-spin text-[rgba(13,13,13,0.35)]" /></div>}
        {!loading && facts.length === 0 && (
          <p className="py-3 text-center text-[12px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.4)]">Нет сохранённых фактов</p>
        )}
        {facts.map((f) => (
          <div key={f.id} className="group flex items-start gap-2 rounded-[7px] px-2 py-1.5 hover:bg-[rgba(124,58,237,0.05)]">
            <span className="flex-1 text-[12px] leading-relaxed text-[rgba(13,13,13,0.75)] dark:text-[rgba(236,236,236,0.7)] line-clamp-2">{f.content}</span>
            <button
              onClick={() => handleDeactivate(f.id)}
              disabled={deactivating.has(f.id)}
              className="mt-0.5 shrink-0 rounded-[5px] p-0.5 text-[rgba(13,13,13,0.3)] hover:bg-red-50 hover:text-red-500 disabled:opacity-40 dark:text-[rgba(236,236,236,0.3)]"
              title="Забыть"
            >
              {deactivating.has(f.id) ? <Loader2 size={12} className="animate-spin" /> : <X size={12} />}
            </button>
          </div>
        ))}
      </div>
      <div className="border-t border-[rgba(13,13,13,0.07)] px-3 py-2 dark:border-[rgba(255,255,255,0.07)]">
        <a href="/account/memory/" className="text-[11px] text-[rgba(10,124,255,0.8)] hover:text-[#0a7cff]">Управление памятью →</a>
      </div>
    </div>
  );
}
