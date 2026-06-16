'use client';

import { useEffect, useRef, useState } from 'react';
import { pipeline } from './styles';

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
    let es: EventSource | null = null;
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (closed) return;
      es = new EventSource(
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
      es.onerror = () => {
        es?.close();
        if (!closed) {
          retryTimer = setTimeout(connect, 3000);
        }
      };
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      es?.close();
    };
  }, [projectId]);

  useEffect(() => {
    ref.current?.scrollTo(0, ref.current.scrollHeight);
  }, [lines]);

  return (
    <div
      ref={ref}
      className={pipeline.log}
    >
      {lines.length === 0 && (
        <span className="opacity-40">Ожидание событий агентов...</span>
      )}
      {lines.map((line, i) => (
        <div
          key={i}
          className={
            line.level === 'error'
              ? pipeline.logLine.error
              : line.level === 'warning'
              ? pipeline.logLine.warning
              : line.level === 'success'
              ? pipeline.logLine.success
              : pipeline.logLine.default
          }
        >
          <span className="opacity-50">[{line.agent}]</span>{' '}
          <span>{line.text}</span>
        </div>
      ))}
    </div>
  );
}
