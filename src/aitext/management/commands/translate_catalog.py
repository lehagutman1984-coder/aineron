"""
Перевод контента каталога на английский (GLOBAL_EXPANSION_PLAN.md §4.3).

Заполняет пустые *_en поля моделей Category / NeuralNetwork / FAQ переводом
русских значений через LLM (laozhang). Уже заполненные *_en не трогает
(ручные правки имеют приоритет). Идемпотентна — можно запускать повторно.

Запуск:
  python manage.py translate_catalog             # всё, что не переведено
  python manage.py translate_catalog --dry-run   # показать объём без API-вызовов
"""
import json
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

MODEL = 'gpt-4o'

SYSTEM_PROMPT = (
    "You are a professional localizer translating a Russian AI-platform catalog to English. "
    "Tone: professional, concise product copy (like Linear/Vercel/Stripe). No exclamation marks, no emoji. "
    "Never translate product/brand names (GPT-4o, Claude, Gemini, Sora, Kling, Veo, DALL-E, aineron, Telegram). "
    "Respond with ONLY a JSON object mapping each input key to its English translation."
)


def _chunks(items, size=25):
    for i in range(0, len(items), size):
        yield items[i:i + size]


class Command(BaseCommand):
    help = 'Переводит контент каталога (Category/NeuralNetwork/FAQ) на английский через laozhang'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from aitext.models import Category, FAQ, NeuralNetwork

        # (объект, ru-поле, en-поле) — только непустой ru и пустой en
        jobs = []

        def collect(qs, fields):
            for obj in qs:
                for f in fields:
                    ru = getattr(obj, f'{f}_ru') or getattr(obj, f) or ''
                    en = getattr(obj, f'{f}_en') or ''
                    if ru.strip() and not en.strip():
                        jobs.append((obj, f, ru.strip()))

        collect(Category.objects.all(), ['name'])
        collect(NeuralNetwork.objects.all(), ['description', 'seo_title', 'seo_description', 'seo_keywords'])
        collect(FAQ.objects.all(), ['question', 'answer'])

        self.stdout.write(f'К переводу: {len(jobs)} полей')
        if options['dry_run'] or not jobs:
            return

        from aitext.providers import _get_raw_client
        client = _get_raw_client('laozhang')

        done = 0
        for batch in _chunks(jobs):
            payload = {f'{i}': ru for i, (_, _, ru) in enumerate(batch)}
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    temperature=0.2,
                    response_format={'type': 'json_object'},
                    messages=[
                        {'role': 'system', 'content': SYSTEM_PROMPT},
                        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
                    ],
                )
                translated = json.loads(resp.choices[0].message.content)
            except Exception as e:
                self.stderr.write(f'Батч пропущен (ошибка API): {e}')
                continue

            for i, (obj, field, _ru) in enumerate(batch):
                value = translated.get(str(i))
                if not isinstance(value, str) or not value.strip():
                    continue
                setattr(obj, f'{field}_en', value.strip())
                obj.save(update_fields=[f'{field}_en'])
                done += 1
            self.stdout.write(f'  переведено {done}/{len(jobs)}')

        self.stdout.write(self.style.SUCCESS(f'Готово: {done} полей переведено.'))
