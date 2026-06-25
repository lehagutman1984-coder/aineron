'use client';

import { useEffect, useState } from 'react';
import { SandpackProvider, SandpackPreview } from '@codesandbox/sandpack-react';
import { studioApi } from '@/lib/api/studio';

type SandpackTemplate = 'react' | 'vue' | 'static';

const STACK_TEMPLATE: Record<string, SandpackTemplate> = {
  react: 'react',
  vue: 'vue',
  html: 'static',
  tma: 'static',
};

// Минимальный мок Telegram.WebApp для предпросмотра TMA без реального Telegram
const TMA_MOCK_SCRIPT = `
window.Telegram = {
  WebApp: {
    ready: function() {},
    expand: function() {},
    close: function() {},
    initData: '',
    initDataUnsafe: { user: { id: 1, first_name: 'Test', last_name: 'User', username: 'testuser', language_code: 'ru' } },
    colorScheme: 'light',
    themeParams: { bg_color: '#ffffff', text_color: '#000000', button_color: '#0088cc', button_text_color: '#ffffff', hint_color: '#999999', link_color: '#0088cc', secondary_bg_color: '#f1f1f1' },
    version: '7.0',
    platform: 'web',
    isExpanded: true,
    viewportHeight: window.innerHeight,
    viewportStableHeight: window.innerHeight,
    sendData: function(data) { console.log('[TMA mock] sendData:', data); },
    showAlert: function(msg, cb) { alert(msg); if (cb) cb(); },
    showConfirm: function(msg, cb) { if (cb) cb(confirm(msg)); },
    MainButton: {
      text: '', color: '#0088cc', textColor: '#ffffff', isVisible: false, isActive: true,
      show: function() { this.isVisible = true; },
      hide: function() { this.isVisible = false; },
      onClick: function(cb) { this._cb = cb; },
      offClick: function() { this._cb = null; },
      setText: function(t) { this.text = t; },
      enable: function() { this.isActive = true; },
      disable: function() { this.isActive = false; },
    },
    BackButton: {
      isVisible: false,
      show: function() { this.isVisible = true; },
      hide: function() { this.isVisible = false; },
      onClick: function(cb) { this._cb = cb; },
      offClick: function() { this._cb = null; },
    },
    HapticFeedback: {
      impactOccurred: function() {},
      notificationOccurred: function() {},
      selectionChanged: function() {},
    },
  }
};
console.log('[aineron] Telegram.WebApp mock injected');
`;

interface Props {
  projectId: string;
  stack: string;
  refreshKey: number;
}

type SandpackFiles = Record<string, { code: string }>;

export function SandpackPreviewPanel({ projectId, stack, refreshKey }: Props) {
  const [files, setFiles] = useState<SandpackFiles | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load() {
      try {
        const nodes = await studioApi.files(projectId);
        if (cancelled || nodes.length === 0) {
          if (!cancelled) setFiles({});
          return;
        }
        const details = await Promise.all(nodes.map((n) => studioApi.fileDetail(projectId, n.id)));
        if (cancelled) return;

        const result: SandpackFiles = {};
        for (const f of details) {
          const path = f.path.startsWith('/') ? f.path : `/${f.path}`;
          result[path] = { code: f.content };
        }

        if (stack === 'tma') {
          result['/tma-mock.js'] = { code: TMA_MOCK_SCRIPT };
        }

        setFiles(result);
      } catch {
        if (!cancelled) setFiles({});
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [projectId, refreshKey]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-[var(--text-secondary)]">
        Загружаю файлы…
      </div>
    );
  }

  if (!files || Object.keys(files).length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-[var(--text-secondary)]">
        Файлы появятся после первого шага кодинга
      </div>
    );
  }

  const template = STACK_TEMPLATE[stack] ?? 'static';

  return (
    <SandpackProvider
      files={files}
      template={template}
      theme="dark"
      options={{ recompileDelay: 500, externalResources: stack === 'tma' ? ['/tma-mock.js'] : [] }}
    >
      <SandpackPreview style={{ height: '100%', width: '100%' }} showOpenInCodeSandbox={false} />
    </SandpackProvider>
  );
}
