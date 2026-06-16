'use client';

import { useEffect, useRef, useState } from 'react';
import { Copy, Check } from 'lucide-react';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';

interface CodeViewerProps {
  content: string;
  language: string;
  path?: string;
}

export function CodeViewer({ content, language, path }: CodeViewerProps) {
  const [copied, setCopied] = useState(false);
  const codeRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (codeRef.current && content) {
      codeRef.current.removeAttribute('data-highlighted');
      hljs.highlightElement(codeRef.current);
    }
  }, [content, language]);

  const handleCopy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (!content) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-[var(--text-secondary)] opacity-60">
        Выберите файл
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {path && (
        <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)] text-xs text-[var(--text-secondary)] shrink-0">
          <span className="font-mono">{path}</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 hover:text-[var(--text)] transition-colors"
          >
            {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
            {copied ? 'Скопировано' : 'Скопировать'}
          </button>
        </div>
      )}
      <div className="flex-1 overflow-auto">
        <pre className="text-xs overflow-auto h-full m-0">
          <code ref={codeRef} className={language ? `language-${language}` : ''}>
            {content}
          </code>
        </pre>
      </div>
    </div>
  );
}
