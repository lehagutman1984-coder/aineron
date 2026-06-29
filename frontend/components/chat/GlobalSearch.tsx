"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, X, MessageSquare, Bot, Clock } from "lucide-react";
import { searchChats } from "@/lib/api/client";
import type { ChatSearchResult } from "@/lib/api/types";

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ChatSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const debouncedQuery = useDebounce(query, 320);

  // Ctrl+K / Cmd+K or custom event from sidebar
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    const onCustom = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("open-global-search", onCustom);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("open-global-search", onCustom);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
      setResults([]);
      setSelected(0);
    }
  }, [open]);

  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 2) {
      setResults([]);
      return;
    }
    setLoading(true);
    searchChats(debouncedQuery)
      .then((r) => { setResults(r.results); setSelected(0); })
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }, [debouncedQuery]);

  const navigate = useCallback(
    (result: ChatSearchResult) => {
      router.push(`/chat/${result.chat_id}`);
      setOpen(false);
    },
    [router]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!results.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setSelected((s) => Math.min(s + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSelected((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); navigate(results[selected]); }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-16 px-4 bg-black/30 backdrop-blur-[2px]"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-xl bg-white dark:bg-[#1a1a1a] border border-[rgba(13,13,13,0.12)] rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Input */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[rgba(13,13,13,0.08)]">
          <Search size={16} className="text-[rgba(13,13,13,0.35)] flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Поиск по истории чатов..."
            className="flex-1 bg-transparent text-sm outline-none text-[#0d0d0d] placeholder:text-[rgba(13,13,13,0.32)]"
          />
          {loading && (
            <div className="w-4 h-4 border-2 border-[#f0a38a] border-t-transparent rounded-full animate-spin flex-shrink-0" />
          )}
          <button onClick={() => setOpen(false)} className="text-[rgba(13,13,13,0.35)] hover:text-[#0d0d0d]">
            <X size={16} />
          </button>
        </div>

        {/* Results */}
        {results.length > 0 && (
          <ul className="max-h-80 overflow-y-auto">
            {results.map((r, i) => (
              <li key={r.message_id}>
                <button
                  onClick={() => navigate(r)}
                  className={`w-full text-left px-4 py-3 flex gap-3 items-start transition-colors ${
                    i === selected ? "bg-[rgba(10,124,255,0.06)]" : "hover:bg-[rgba(13,13,13,0.03)]"
                  }`}
                >
                  <div className="flex-shrink-0 mt-0.5">
                    {r.role === "user"
                      ? <MessageSquare size={14} className="text-[#f0a38a]" />
                      : <Bot size={14} className="text-[rgba(13,13,13,0.40)]" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-[12px] font-medium text-[#0d0d0d] truncate">{r.chat_title}</span>
                      <span className="text-[10px] text-[rgba(13,13,13,0.40)] flex-shrink-0">{r.network_name}</span>
                    </div>
                    <p className="text-[11px] text-[rgba(13,13,13,0.60)] line-clamp-2 leading-relaxed">{r.snippet}</p>
                  </div>
                  <div className="flex-shrink-0 flex items-center gap-0.5 text-[rgba(13,13,13,0.30)]">
                    <Clock size={10} />
                    <span className="text-[10px]">
                      {new Date(r.created_at).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}
                    </span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}

        {!loading && query.length >= 2 && results.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-[rgba(13,13,13,0.45)]">
            Ничего не найдено по запросу «{query}»
          </div>
        )}

        {!query && (
          <div className="px-4 py-5 text-[12px] text-[rgba(13,13,13,0.40)] text-center">
            Введите запрос для поиска по истории всех чатов
          </div>
        )}

        <div className="px-4 py-2 border-t border-[rgba(13,13,13,0.06)] flex items-center gap-3 text-[10px] text-[rgba(13,13,13,0.30)]">
          <span><kbd className="bg-[rgba(13,13,13,0.07)] px-1 py-0.5 rounded text-[9px]">↑↓</kbd> навигация</span>
          <span><kbd className="bg-[rgba(13,13,13,0.07)] px-1 py-0.5 rounded text-[9px]">Enter</kbd> открыть</span>
          <span><kbd className="bg-[rgba(13,13,13,0.07)] px-1 py-0.5 rounded text-[9px]">Esc</kbd> закрыть</span>
        </div>
      </div>
    </div>
  );
}
