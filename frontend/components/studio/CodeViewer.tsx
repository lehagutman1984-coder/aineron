'use client';

import { useEffect, useState } from 'react';
import { Copy, Check, Save, Sparkles, X } from 'lucide-react';
import CodeMirror from '@uiw/react-codemirror';
import { javascript } from '@codemirror/lang-javascript';
import { html } from '@codemirror/lang-html';
import { css } from '@codemirror/lang-css';
import { oneDark } from '@codemirror/theme-one-dark';
import ReactMarkdown from 'react-markdown';
import { studioApi } from '@/lib/api/studio';
import { code, empty } from './styles';

interface CodeViewerProps {
  content: string;
  language: string;
  path?: string;
  editable?: boolean;
  onSave?: (content: string) => Promise<void> | void;
  projectId?: string;
  streaming?: boolean;
  streamContent?: string;
}

function extToLang(path?: string) {
  if (!path) return javascript({ jsx: true, typescript: true });
  if (path.endsWith('.html')) return html();
  if (path.endsWith('.css')) return css();
  return javascript({ jsx: true, typescript: true });
}

export function CodeViewer({ content, language: _language, path, editable, onSave, projectId, streaming, streamContent }: CodeViewerProps) {
  const [copied, setCopied] = useState(false);
  const [value, setValue] = useState(content);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [selection, setSelection] = useState('');
  const [explanation, setExplanation] = useState<string | null>(null);
  const [explaining, setExplaining] = useState(false);

  useEffect(() => { setValue(content); setDirty(false); }, [content, path]);

  // Live streaming: show streamContent while coder is actively writing this file
  const displayValue = (streaming && streamContent != null) ? streamContent : value;

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

  const onMouseUp = () => {
    const sel = window.getSelection()?.toString() ?? '';
    setSelection(sel.trim());
  };

  const runExplain = async () => {
    if (!projectId || !selection) return;
    setExplaining(true);
    try {
      const res = await studioApi.explain(projectId, selection, path);
      setExplanation(res.explanation);
    } finally {
      setExplaining(false);
    }
  };

  if (!content && !editable) {
    return (
      <div className={empty.center}>
        Выберите файл
      </div>
    );
  }

  return (
    <div className={code.root}>
      {path && (
        <div className={code.pathBar}>
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
      <div className={code.editor} onMouseUp={onMouseUp}>
        <CodeMirror
          value={displayValue}
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

      {/* Floating explain button when text is selected */}
      {projectId && selection && !explanation && (
        <div className="absolute bottom-4 right-4 z-10">
          <button
            onClick={runExplain}
            disabled={explaining}
            className={code.explainBtn}
          >
            <Sparkles size={13} />
            {explaining ? 'Анализирую…' : 'Объясни'}
          </button>
        </div>
      )}

      {/* Explanation popover */}
      {explanation && (
        <div className={code.popover}>
          <div className="flex items-center justify-between mb-2">
            <span className="font-medium flex items-center gap-1"><Sparkles size={12} /> Объяснение</span>
            <button
              onClick={() => { setExplanation(null); setSelection(''); }}
              className="text-[var(--text-secondary)] hover:text-[var(--text)]"
            >
              <X size={14} />
            </button>
          </div>
          <div className="prose prose-xs dark:prose-invert max-w-none text-[var(--text)]">
            <ReactMarkdown>{explanation}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
