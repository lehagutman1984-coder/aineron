"""
LLM-пайплайн перевода словарей Telegram-бота (GLOBAL_EXPANSION_PLAN.md §4.6).

Тот же принцип, что и frontend/scripts/translate-locales.mjs: источник —
locales/en.json (уже адаптирован под aineron.net — крипта/кредиты, без
рублей/Robokassa), НЕ ru.json (там инвентарь под aineron.ru).

Запуск: python manage.py translate_bot_locales fa tr
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings


LOCALES_DIR = Path(__file__).resolve().parent.parent.parent / 'locales'
LOCALE_NAMES = {
    'fa': 'Persian (Farsi)',
    'tr': 'Turkish',
    'id': 'Indonesian',
    'ar': 'Arabic (Modern Standard)',
}
DO_NOT_TRANSLATE = ['Aineron', 'aineron', 'GPT-4o', 'Claude', 'Gemini', 'HTML']


def flatten(obj, prefix=''):
    out = {}
    for k, v in obj.items():
        key = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = v
    return out


def unflatten(flat):
    out = {}
    for key, value in flat.items():
        parts = key.split('.')
        node = out
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value
    return out


class Command(BaseCommand):
    help = 'Translate telegram_bot/locales/en.json into target locales via laozhang.ai'

    def add_arguments(self, parser):
        parser.add_argument('locales', nargs='*', default=list(LOCALE_NAMES.keys()))

    def handle(self, *args, **options):
        import requests

        api_key = getattr(settings, 'LAOZHANG_API_KEY', '') or __import__('os').environ.get('LAOZHANG_API_KEY', '')
        if not api_key:
            self.stderr.write('LAOZHANG_API_KEY not set')
            return

        source = json.loads((LOCALES_DIR / 'en.json').read_text(encoding='utf-8'))
        source_flat = flatten(source)

        for locale in options['locales']:
            if locale not in LOCALE_NAMES:
                self.stderr.write(f'Unknown locale: {locale}')
                continue

            system_prompt = (
                f"You are a professional UI localizer translating a Telegram bot interface "
                f"from English to {LOCALE_NAMES[locale]}.\n"
                f"Tone: professional, concise, no exclamation marks, no emoji.\n"
                f"NEVER translate these terms (keep verbatim): {', '.join(DO_NOT_TRANSLATE)}.\n"
                f"Preserve HTML tags (<b>, <i>, <code>) and all {{placeholder}} tokens exactly.\n"
                f"Preserve literal slash-commands (/balance, /models, /image, /settings, /newchat) "
                f"and URLs (aineron.net/...) exactly, untranslated.\n"
                f"Respond with ONLY a JSON object mapping each input key to its translation."
            )
            user_prompt = json.dumps(source_flat, ensure_ascii=False, indent=2)

            resp = requests.post(
                f"{getattr(settings, 'LAOZHANG_API_URL', 'https://api.laozhang.ai/v1')}/chat/completions",
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                json={
                    'model': 'gpt-4o',
                    'temperature': 0.2,
                    'response_format': {'type': 'json_object'},
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt},
                    ],
                },
                timeout=180,
            )
            resp.raise_for_status()
            translated = json.loads(resp.json()['choices'][0]['message']['content'])

            missing = [k for k in source_flat if k not in translated or not translated[k].strip()]
            if missing:
                self.stderr.write(f'[{locale}] missing/empty: {missing}')
                for k in missing:
                    translated[k] = source_flat[k]  # fallback to English rather than blank

            out_path = LOCALES_DIR / f'{locale}.json'
            out_path.write_text(
                json.dumps(unflatten(translated), ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
            self.stdout.write(f'[{locale}] written: {out_path} ({len(translated)} keys)')
