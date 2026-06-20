"""
Статический scaffold UI-примитивов для V3. Записывается детерминированно
на шаге 0, чтобы не доверять качество базовых компонентов LLM.
Зависит только от Tailwind + lucide-react (без shadcn/radix).
"""

_BUTTON = """import { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

const styles: Record<Variant, string> = {
  primary: 'bg-primary text-white hover:opacity-90',
  secondary: 'bg-muted text-foreground hover:bg-muted/80',
  ghost: 'bg-transparent hover:bg-muted',
}

export function Button({ variant = 'primary', className = '', ...props }: Props) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg h-10 px-4 text-sm font-medium transition disabled:opacity-50 ${styles[variant]} ${className}`}
      {...props}
    />
  )
}
"""

_CARD = """import { HTMLAttributes } from 'react'

export function Card({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`rounded-xl border border-border bg-card p-6 shadow-sm ${className}`} {...props} />
  )
}
"""

_INPUT = """import { InputHTMLAttributes } from 'react'

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-lg border border-border bg-background h-10 px-3 text-sm outline-none focus:ring-2 focus:ring-primary ${className}`}
      {...props}
    />
  )
}
"""

_BADGE = """import { HTMLAttributes } from 'react'

export function Badge({ className = '', ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={`inline-flex items-center rounded-md border border-border px-2 py-0.5 text-xs font-medium ${className}`} {...props} />
  )
}
"""


def scaffold_files(stack: str, design_md: str = '') -> dict:
    """
    Возвращает {path: content} стартовых UI-примитивов для react/nextjs.
    Для vue/html — пустой dict (примитивы не применяются).
    """
    if stack not in ('react', 'nextjs'):
        return {}
    base = 'src/components/ui'
    return {
        f'{base}/Button.tsx': _BUTTON,
        f'{base}/Card.tsx': _CARD,
        f'{base}/Input.tsx': _INPUT,
        f'{base}/Badge.tsx': _BADGE,
    }


# ─── Russian integration scaffolds (V4) ──────────────────────────────────────

_ROBOKASSA_HOOK = """\
// Robokassa payment helper (Aineron Studio scaffold)
// Sends order to Django backend; backend returns redirect URL to Robokassa
export async function startRobokassaPayment(params: {
  amount: number;
  description: string;
  orderId?: string;
}) {
  const res = await fetch('/api/payments/robokassa/init/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await res.text());
  const { redirect_url } = await res.json();
  window.location.href = redirect_url;
}
"""

_VK_ID_SNIPPET = """\
<!-- VK ID widget (Aineron Studio scaffold) -->
<!-- Replace APP_ID with your VK application ID from vk.com/apps -->
<div id="VKIDSDKAuthButton"></div>
<script type="module">
  import VKID from 'https://unpkg.com/@vkid/sdk/dist-sdk/umd/index.js';
  VKID.Config.init({
    app: APP_ID,
    redirectUrl: window.location.origin + '/auth/vk/callback/',
  });
  const oneTap = new VKID.OneTap();
  oneTap.render({ container: document.getElementById('VKIDSDKAuthButton') });
  oneTap.on(VKID.WidgetEvents.ERROR, console.error);
</script>
"""

_YANDEX_MAPS_COMPONENT = """\
import { useEffect, useRef } from 'react';

declare global {
  interface Window { ymaps3: typeof import('@yandex/ymaps3-types'); }
}

interface YandexMapProps {
  center?: [number, number];
  zoom?: number;
  apiKey: string;
}

export function YandexMap({ center = [55.75, 37.62], zoom = 10, apiKey }: YandexMapProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const script = document.createElement('script');
    // Replace YOUR_YANDEX_MAPS_API_KEY or pass apiKey prop
    script.src = `https://api-maps.yandex.ru/v3/?apikey=${apiKey}&lang=ru_RU`;
    script.onload = async () => {
      await window.ymaps3.ready;
      const { YMap, YMapDefaultSchemeLayer } = window.ymaps3;
      const map = new YMap(ref.current!, { location: { center, zoom } });
      map.addChild(new YMapDefaultSchemeLayer({}));
    };
    document.head.appendChild(script);
    return () => { document.head.removeChild(script); };
  }, [apiKey]);

  return <div ref={ref} style={{ width: '100%', height: '400px' }} />;
}
"""

_TELEGRAM_LOGIN_COMPONENT = """\
import { useEffect } from 'react';

interface TelegramUser {
  id: number; first_name: string; username?: string; photo_url?: string;
}
interface TelegramLoginProps {
  botName: string;
  onAuth: (user: TelegramUser) => void;
  buttonSize?: 'large' | 'medium' | 'small';
}

declare global {
  interface Window { TelegramLoginWidget: { dataOnauth: (user: TelegramUser) => void }; }
}

export function TelegramLogin({ botName, onAuth, buttonSize = 'medium' }: TelegramLoginProps) {
  useEffect(() => {
    window.TelegramLoginWidget = { dataOnauth: onAuth };
    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.setAttribute('data-telegram-login', botName);
    script.setAttribute('data-size', buttonSize);
    script.setAttribute('data-onauth', 'TelegramLoginWidget.dataOnauth(user)');
    script.setAttribute('data-request-access', 'write');
    script.async = true;
    document.getElementById('tg-login-widget')?.appendChild(script);
    return () => { document.getElementById('tg-login-widget')?.replaceChildren(); };
  }, [botName, onAuth, buttonSize]);

  return <div id="tg-login-widget" />;
}
"""


_TMA_VITE_CONFIG = """\
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Telegram Mini App scaffold — Vite + React
// @twa-dev/sdk provides WebApp methods and initData
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 3000 },
  base: './',
  build: { outDir: 'dist', sourcemap: false },
});
"""

_TMA_APP_TSX = """\
import { useEffect, useState } from 'react';
import WebApp from '@twa-dev/sdk';

// Main TMA entry point — runs inside Telegram
// Call WebApp.ready() FIRST so Telegram hides the loading spinner
export default function App() {
  const [user, setUser] = useState<{ first_name: string } | null>(null);

  useEffect(() => {
    WebApp.ready();
    WebApp.expand();
    setUser(WebApp.initDataUnsafe?.user ?? null);
  }, []);

  return (
    <div style={{ padding: 16, fontFamily: 'sans-serif' }}>
      <h1>Hello, {user?.first_name ?? 'User'}!</h1>
    </div>
  );
}
"""

_TMA_VALIDATE_PY = """\
# validate_tma_init_data.py — server-side HMAC validation (mandatory per Telegram docs)
# Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
import hashlib
import hmac
import urllib.parse


def validate_init_data(init_data: str, bot_token: str) -> bool:
    \"\"\"Validate Telegram Mini App initData string.\"\"\"
    params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    hash_value = params.pop('hash', '')
    data_check_string = '\\n'.join(f'{k}={v}' for k, v in sorted(params.items()))
    secret_key = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, hash_value)
"""

_TMA_PACKAGE_JSON = """\
{
  "name": "tma-app",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 3000",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "@twa-dev/sdk": "^7.10.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.7.2",
    "vite": "^6.0.5"
  }
}
"""

_TMA_PAYMENTS_TSX = """\
import WebApp from '@twa-dev/sdk';

// Telegram Stars payment via Telegram's native invoicing
// Backend must create invoice link: https://core.telegram.org/bots/api#createinvoicelink
interface PaymentParams {
  title: string;
  amount: number;  // in Telegram Stars (XTR)
  invoiceUrl?: string;  // optional: pre-generated invoice URL from backend
}

export async function openTelegramPayment({ title, amount, invoiceUrl }: PaymentParams) {
  if (invoiceUrl) {
    WebApp.openInvoice(invoiceUrl, (status) => {
      if (status === 'paid') {
        WebApp.showAlert(`Оплачено ${amount} Stars!`);
      } else if (status === 'failed') {
        WebApp.showAlert('Оплата не прошла. Попробуйте снова.');
      }
    });
    return;
  }
  // Fallback: request invoice from backend
  const res = await fetch('/api/tma/invoice/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json',
                'X-Telegram-Init-Data': WebApp.initData },
    body: JSON.stringify({ title, amount }),
  });
  const { invoice_url } = await res.json();
  WebApp.openInvoice(invoice_url, (status) => {
    if (status === 'paid') WebApp.showAlert(`Оплачено ${amount} Stars!`);
  });
}
"""


def scaffold_tma() -> dict:
    """Scaffold for Telegram Mini App (Vite+React+@twa-dev/sdk)."""
    return {
        'vite.config.ts': _TMA_VITE_CONFIG,
        'package.json': _TMA_PACKAGE_JSON,
        'src/App.tsx': _TMA_APP_TSX,
        'src/validate_tma_init_data.py': _TMA_VALIDATE_PY,
    }


def scaffold_tma_payments() -> dict:
    """Scaffold Telegram Stars payment flow."""
    return {'src/lib/tmaPayments.ts': _TMA_PAYMENTS_TSX}


def scaffold_for_features(stack: str, features: list) -> dict:
    """Dispatch Russian integration scaffolds based on feature key list."""
    _FMAP = {
        'robokassa': lambda: scaffold_robokassa(),
        'vk_id': lambda: scaffold_vk_id(),
        'yandex_maps': lambda: scaffold_yandex_maps(),
        'telegram_login': lambda: scaffold_telegram_login(),
        'tma_payments': lambda: scaffold_tma_payments(),
    }
    out: dict = {}
    for feat in (features or []):
        fn = _FMAP.get(feat)
        if fn:
            out.update(fn())
    return out


def scaffold_robokassa() -> dict:
    return {'src/lib/robokassa.ts': _ROBOKASSA_HOOK}


def scaffold_vk_id() -> dict:
    return {'src/components/VKIDButton.html': _VK_ID_SNIPPET}


def scaffold_yandex_maps() -> dict:
    return {'src/components/YandexMap.tsx': _YANDEX_MAPS_COMPONENT}


def scaffold_telegram_login() -> dict:
    return {'src/components/TelegramLogin.tsx': _TELEGRAM_LOGIN_COMPONENT}
