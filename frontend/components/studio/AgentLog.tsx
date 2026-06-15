'use client';

import { useEffect, useRef, useState } from 'react';

interface LogLine {
  agent: string;
  level: string;
  text: string;
  type?: string;
}

interface AgentLogProps {
  projectId: string;
}

export function AgentLog({ projectId }: AgentLogProps) {
  const [lines, setLines] = useState<LogLine[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? '';
    const es = new EventSource(
      `${base}/studio/projects/${projectId}/events/`,
      { withCredentials: true },
    );
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type !== 'connected') {
          setLines((prev) => [...prev, data]);
        }
      } catch {}
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [projectId]);

  useEffect(() => {
    ref.current?.scrollTo(0, ref.current.scrollHeight);
  }, [lines]);

  return (
    <div
      ref={ref}
      className="font-mono text-xs overflow-auto p-3 h-full bg-[var(--card-bg)]"
    >
      {lines.length === 0 && (
        <span className="opacity-40">Ожидание событий агентов...</span>
      )}
      {lines.map((line, i) => (
        <div
          key={i}
          className={
            line.level === 'error'
              ? 'text-red-400'
              : line.level === 'warning'
              ? 'text-yellow-400'
              : line.level === 'success'
              ? 'text-green-400'
              : 'text-[var(--text)]'
          }
        >
          <span className="opacity-50">[{line.agent}]</span>{' '}
          <span>{line.text}</span>
        </div>
      ))}
    </div>
  );
}
