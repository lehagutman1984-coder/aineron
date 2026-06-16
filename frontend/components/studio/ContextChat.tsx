'use client';

import { useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { AlertTriangle, Play, SkipForward, ArrowRight, Loader2, Send } from 'lucide-react';
import { AgentLog } from './AgentLog';
import { studioApi } from '@/lib/api/studio';

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
}

interface ContextChatProps {
  projectId: string;
  pauseReason: string;
  resumeHint: string;
  onResume: () => void;
}

export function ContextChat({ projectId, pauseReason, resumeHint, onResume }: ContextChatProps) {
  const [hint, setHint] = useState(resumeHint ?? '');
  const [resumeLoading, setResumeLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const chatMutation = useMutation({
    mutationFn: (message: string) => studioApi.contextChat(projectId, message),
    onSuccess: (data, message) => {
      setChatMessages((prev) => [
        ...prev,
        { role: 'user', text: message },
        { role: 'assistant', text: data.answer },
      ]);
      setChatInput('');
      setTimeout(() => chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    },
  });

  const sendChat = () => {
    const msg = chatInput.trim();
    if (!msg || chatMutation.isPending) return;
    chatMutation.mutate(msg);
  };

  const resume = async (action: 'continue' | 'with_hint' | 'skip_step') => {
    setResumeLoading(true);
    try {
      await studioApi.resume(projectId, { action, hint: action === 'with_hint' ? hint : undefined });
      onResume();
    } finally {
      setResumeLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-start gap-3 p-4 border-b border-[var(--border)] bg-red-950/30 shrink-0">
        <AlertTriangle size={18} className="text-red-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-red-400">Пайплайн остановлен</p>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">{pauseReason}</p>
        </div>
      </div>

      {/* LLM chat */}
      {chatMessages.length > 0 && (
        <div className="flex-shrink-0 max-h-48 overflow-auto p-3 space-y-2 border-b border-[var(--border)]">
          {chatMessages.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
              <span
                className={`inline-block px-3 py-1.5 rounded-lg text-xs max-w-[85%] ${
                  m.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text)]'
                }`}
              >
                {m.text}
              </span>
            </div>
          ))}
          <div ref={chatBottomRef} />
        </div>
      )}

      <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border)] shrink-0">
        <input
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendChat()}
          placeholder="Спросите ассистента... (1 звезда)"
          className="flex-1 bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={sendChat}
          disabled={chatMutation.isPending || !chatInput.trim()}
          className="p-1.5 text-blue-500 hover:text-blue-400 disabled:opacity-40 transition-colors"
        >
          {chatMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </div>

      <div className="flex-1 overflow-auto min-h-0">
        <AgentLog projectId={projectId} />
      </div>

      <div className="p-4 border-t border-[var(--border)] space-y-3 shrink-0">
        <textarea
          value={hint}
          onChange={(e) => setHint(e.target.value)}
          placeholder="Подсказка для кодера (необязательно)..."
          rows={2}
          className="w-full border border-[var(--border)] bg-[var(--input-bg)] rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => resume('with_hint')}
            disabled={resumeLoading || !hint.trim()}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-3 py-2 rounded-lg text-xs font-medium transition-colors"
          >
            <ArrowRight size={14} />
            С подсказкой
          </button>
          <button
            onClick={() => resume('continue')}
            disabled={resumeLoading}
            className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-2 rounded-lg text-xs font-medium transition-colors"
          >
            <Play size={14} />
            Продолжить
          </button>
          <button
            onClick={() => resume('skip_step')}
            disabled={resumeLoading}
            className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-2 rounded-lg text-xs font-medium transition-colors"
          >
            <SkipForward size={14} />
            Пропустить шаг
          </button>
        </div>
      </div>
    </div>
  );
}
