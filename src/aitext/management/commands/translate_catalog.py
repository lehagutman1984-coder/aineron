"""
Перевод контента каталога (GLOBAL_EXPANSION_PLAN.md §4.3, §5 G5).

Заполняет пустые *_{locale} поля моделей Category / NeuralNetwork / FAQ /
PromptTemplate (только встроенные, user=None) переводом через LLM (laozhang).
Уже заполненные поля не трогает (ручные правки имеют приоритет). Идемпотентна
— можно запускать повторно.

Запуск:
  python manage.py translate_catalog                       # en из ru (умолчание, как раньше)
  python manage.py translate_catalog fa tr id ar --source=en  # G5: волна 1 из en (без RU-специфики)
  python manage.py translate_catalog --dry-run             # показать объём без API-вызовов

--source=en ОБЯЗАТЕЛЕН для fa/tr/id/ar — тот же принцип, что и в
frontend/scripts/translate-locales.mjs и translate_bot_locales: ru.json
несёт РФ-специфику (рубли и т.п.), en уже адаптирован под aineron.net.
"""
import json
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

MODEL = 'gpt-4o'

LOCALE_NAMES = {
    'en': 'English',
    'fa': 'Persian (Farsi)',
    'tr': 'Turkish',
    'id': 'Indonesian',
    'ar': 'Arabic (Modern Standard)',
}

# django-modeltranslation мапит ISO 'id' → суффикс поля 'ind' (избегает
# коллизии с конвенцией *_id для внешних ключей).
FIELD_SUFFIX = {'id': 'ind'}

DO_NOT_TRANSLATE = ['GPT-4o', 'Claude', 'Gemini', 'Sora', 'Kling', 'Veo', 'DALL-E', 'aineron', 'Telegram']


def _chunks(items, size=25):
    for i in range(0, len(items), size):
        yield items[i:i + size]


class Command(BaseCommand):
    help = 'Переводит контент каталога (Category/NeuralNetwork/FAQ) через laozhang'

    def add_arguments(self, parser):
        parser.add_argument('locales', nargs='*', default=['en'])
        parser.add_argument('--source', default='ru', choices=['ru', 'en'])
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from aitext.models import Category, FAQ, NeuralNetwork, PromptTemplate

        source = options['source']
        source_suffix = FIELD_SUFFIX.get(source, source)
        locales = options['locales']
        unknown = [loc for loc in locales if loc not in LOCALE_NAMES]
        if unknown:
            self.stderr.write(f'Неизвестные локали: {unknown}. Доступны: {list(LOCALE_NAMES)}')
            return

        from aitext.providers import _get_raw_client
        client = _get_raw_client('laozhang')

        for locale in locales:
            target_suffix = FIELD_SUFFIX.get(locale, locale)
            system_prompt = (
                f"You are a professional localizer translating an AI-platform's catalog "
                f"content and built-in prompt templates to {LOCALE_NAMES[locale]}.\n"
                f"Tone: professional, concise product copy (like Linear/Vercel/Stripe). "
                f"No exclamation marks, no emoji.\n"
                f"Never translate these terms (keep verbatim): {', '.join(DO_NOT_TRANSLATE)}.\n"
                f"Some inputs are prompt template bodies: preserve markdown code fences "
                f"(```) and their contents verbatim; translate bracketed placeholder "
                f"instructions like [paste your code] into natural phrasing in the target "
                f"language, keeping the brackets.\n"
                f"Respond with ONLY a JSON object mapping each input key to its translation."
            )

            jobs = []

            def collect_fields(qs, fields):
                for obj in qs:
                    for f in fields:
                        # «Сырое» поле — фолбэк ТОЛЬКО для source=ru (исходное поведение
                        # команды, LANGUAGE_CODE инстанса == 'ru' на aineron.ru, где
                        # этот путь и используется). Для source=en фолбэк на сырое поле
                        # опасен: он LANGUAGE_CODE-зависим и может незаметно подставить
                        # русский текст туда, где явно нужен en-source без РФ-специфики.
                        src = getattr(obj, f'{f}_{source_suffix}', '') or ''
                        if not src and source == 'ru':
                            src = getattr(obj, f, '') or ''
                        dst = getattr(obj, f'{f}_{target_suffix}', '') or ''
                        if src.strip() and not dst.strip():
                            jobs.append((obj, f, src.strip()))

            collect_fields(Category.objects.all(), ['name'])
            collect_fields(NeuralNetwork.objects.all(), ['description', 'seo_title', 'seo_description', 'seo_keywords'])
            collect_fields(FAQ.objects.all(), ['question', 'answer'])
            # Только встроенные промты (user=None) — пользовательские шаблоны
            # переводить нельзя, это чужой авторский текст на своём языке.
            collect_fields(PromptTemplate.objects.filter(user__isnull=True), ['title', 'content'])

            self.stdout.write(f'[{locale}] к переводу (источник {source}): {len(jobs)} полей')
            if options['dry_run'] or not jobs:
                continue

            done = 0
            for batch in _chunks(jobs):
                payload = {f'{i}': src for i, (_, _, src) in enumerate(batch)}
                try:
                    resp = client.chat.completions.create(
                        model=MODEL,
                        temperature=0.2,
                        response_format={'type': 'json_object'},
                        messages=[
                            {'role': 'system', 'content': system_prompt},
                            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
                        ],
                    )
                    translated = json.loads(resp.choices[0].message.content)
                except Exception as e:
                    self.stderr.write(f'[{locale}] батч пропущен (ошибка API): {e}')
                    continue

                for i, (obj, field, _src) in enumerate(batch):
                    value = translated.get(str(i))
                    if not isinstance(value, str) or not value.strip():
                        continue
                    setattr(obj, f'{field}_{target_suffix}', value.strip())
                    obj.save(update_fields=[f'{field}_{target_suffix}'])
                    done += 1
                self.stdout.write(f'  [{locale}] переведено {done}/{len(jobs)}')

            self.stdout.write(self.style.SUCCESS(f'[{locale}] готово: {done} полей переведено.'))
