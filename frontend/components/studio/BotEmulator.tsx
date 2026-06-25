'use client';

import { useRef, useState } from 'react';
import { Bot, Send } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';

interface Message {
  role: 'user' | 'bot';
  text: string;
}

interface Props {
  projectId: string;
}

export function BotEmulator({ projectId }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'bot', text: 'Привет! Напишите /start или любое сообщение для симуляции бота.' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text }]);
    setLoading(true);
    try {
      const r = await studioApi.botEmulate(projectId, text);
      setMessages((prev) => [...prev, { role: 'bot', text: r.reply }]);
    } catch {
      setMessages((prev) => [...prev, { role: 'bot', text: '[Ошибка симуляции — нет файлов или LLM недоступен]' }]);
    } finally {
      setLoading(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border)] bg-[var(--hover)] shrink-0">
        <Bot size={14} className="text-[var(--text-secondary)]" />
        <span className="text-xs text-[var(--text-secondary)]">Tier 1 — AI-симулятор, бот не запущен</span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'bg-blue-500 text-white rounded-br-sm'
                  : 'bg-[var(--hover)] text-[var(--text)] rounded-bl-sm border border-[var(--border)]'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-[var(--hover)] text-[var(--text-secondary)] rounded-2xl rounded-bl-sm px-3 py-2 text-sm border border-[var(--border)]">
              <span className="animate-pulse">…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="flex items-center gap-2 px-3 py-2 border-t border-[var(--border)] shrink-0">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Сообщение..."
          className="flex-1 bg-[var(--hover)] rounded-full px-3 py-1.5 text-sm outline-none text-[var(--text)] placeholder:text-[var(--text-secondary)] border border-[var(--border)]"
        />
        <button
          onClick={send}
          disabled={!input.trim() || loading}
          className="p-1.5 rounded-full bg-blue-500 text-white disabled:opacity-40 hover:bg-blue-400 transition-colors"
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}
