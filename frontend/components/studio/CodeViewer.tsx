'use client';

import { useEffect, useState } from 'react';
import { Copy, Check, Save } from 'lucide-react';
import CodeMirror from '@uiw/react-codemirror';
import { javascript } from '@codemirror/lang-javascript';
import { html } from '@codemirror/lang-html';
import { css } from '@codemirror/lang-css';
import { oneDark } from '@codemirror/theme-one-dark';

interface CodeViewerProps {
  content: string;
  language: string;
  path?: string;
  editable?: boolean;
  onSave?: (content: string) => Promise<void> | void;
}

function extToLang(path?: string) {
  if (!path) return javascript({ jsx: true, typescript: true });
  if (path.endsWith('.html')) return html();
  if (path.endsWith('.css')) return css();
  return javascript({ jsx: true, typescript: true });
}

export function CodeViewer({ content, language: _language, path, editable, onSave }: CodeViewerProps) {
  const [copied, setCopied] = useState(false);
  const [value, setValue] = useState(content);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => { setValue(content); setDirty(false); }, [content, path]);

  const handleCopy = () => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleSave = async () => {
    if (!onSave || !dirty) return;
    setSaving(true);
    try { await onSave(value); setDirty(false); } finally { setSaving(false); }
  };

  if (!content && !editable) {
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
          <span className="font-mono">{path}{dirty ? ' •' : ''}</span>
          <div className="flex items-center gap-3">
            {editable && (
              <button onClick={handleSave} disabled={!dirty || saving} className="flex items-center gap-1 hover:text-[var(--text)] disabled:opacity-40 transition-colors">
                <Save size={14} />{saving ? 'Сохранение…' : 'Сохранить'}
              </button>
            )}
            <button onClick={handleCopy} className="flex items-center gap-1 hover:text-[var(--text)] transition-colors">
              {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
              {copied ? 'Скопировано' : 'Скопировать'}
            </button>
          </div>
        </div>
      )}
      <div className="flex-1 overflow-auto">
        <CodeMirror
          value={value}
          theme={oneDark}
          editable={!!editable}
          extensions={[extToLang(path)]}
          onChange={(v) => { setValue(v); setDirty(true); }}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); handleSave(); }
          }}
          style={{ height: '100%', fontSize: '12px' }}
        />
      </div>
    </div>
  );
}
