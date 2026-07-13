# -*- coding: utf-8 -*-
"""
Переводит title_en/content_en юр-документов (LegalDocument, seed_intl_legal_docs)
на fa/tr/id/ar через LLM (laozhang) — GLOBAL_EXPANSION_PLAN.md G5.

content — HTML (h2/p/ul/li), переводим одним запросом на документ, чтобы
модель видела текст целиком (для связности юридического языка), но явно
просим сохранить HTML-теги и атрибуты неизменными.

--source=en ОБЯЗАТЕЛЕН: en-документ (seed_intl_legal_docs) уже независим от
российской юрисдикции (крипта-оплата, без реквизитов исполнителя) — тот же
принцип, что и в translate_catalog/translate-locales.mjs.

Запуск:
  python manage.py translate_legal_docs fa tr id ar --source=en
  python manage.py translate_legal_docs --dry-run
  python manage.py translate_legal_docs fa --force   # перевести заново
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

# django-modeltranslation мапит ISO 'id' → суффикс 'ind' (избегает коллизии
# с конвенцией *_id для внешних ключей).
FIELD_SUFFIX = {'id': 'ind'}


class Command(BaseCommand):
    help = 'Переводит title/content юр-документов (LegalDocument) через laozhang'

    def add_arguments(self, parser):
        parser.add_argument('locales', nargs='*', default=['en'])
        parser.add_argument('--source', default='ru', choices=['ru', 'en'])
        parser.add_argument('--force', action='store_true')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from users.models import LegalDocument

        source = options['source']
        source_suffix = FIELD_SUFFIX.get(source, source)
        locales = options['locales']
        unknown = [loc for loc in locales if loc not in LOCALE_NAMES]
        if unknown:
            self.stderr.write(f'Неизвестные локали: {unknown}. Доступны: {list(LOCALE_NAMES)}')
            return

        from aitext.providers import _get_raw_client
        client = _get_raw_client('laozhang')

        docs = list(LegalDocument.objects.all())

        for locale in locales:
            target_suffix = FIELD_SUFFIX.get(locale, locale)
            system_prompt = (
                f"You are a professional legal translator localizing a SaaS Terms of "
                f"Service / Privacy Policy document from {LOCALE_NAMES[source]} to "
                f"{LOCALE_NAMES[locale]}.\n"
                f"Register: formal, precise legal language appropriate for a binding "
                f"user agreement in your language.\n"
                f"The content is HTML. Preserve ALL HTML tags, attributes and structure "
                f"EXACTLY as given (h2, p, ul, li, strong, a href=...) — translate only "
                f"the human-readable text between tags.\n"
                f"Never translate: aineron, Crypto Pay, @CryptoBot, USDT, TON, and any "
                f"email address.\n"
                f"Respond with ONLY a JSON object: {{\"title\": \"...\", \"content\": \"...\"}}."
            )

            jobs = []
            for doc in docs:
                src_title = getattr(doc, f'title_{source_suffix}', '') or ''
                src_content = getattr(doc, f'content_{source_suffix}', '') or ''
                if source == 'ru':
                    src_title = src_title or (doc.title or '')
                    src_content = src_content or (doc.content or '')
                dst_content = getattr(doc, f'content_{target_suffix}', '') or ''
                if src_title.strip() and src_content.strip() and (options['force'] or not dst_content.strip()):
                    jobs.append((doc, src_title.strip(), src_content.strip()))

            self.stdout.write(f'[{locale}] к переводу (источник {source}): {len(jobs)} документов')
            if options['dry_run'] or not jobs:
                continue

            for doc, src_title, src_content in jobs:
                try:
                    resp = client.chat.completions.create(
                        model=MODEL,
                        temperature=0.2,
                        response_format={'type': 'json_object'},
                        messages=[
                            {'role': 'system', 'content': system_prompt},
                            {'role': 'user', 'content': json.dumps(
                                {'title': src_title, 'content': src_content}, ensure_ascii=False,
                            )},
                        ],
                    )
                    translated = json.loads(resp.choices[0].message.content)
                except Exception as e:
                    self.stderr.write(f'[{locale}] {doc.document_type}: пропущен (ошибка API): {e}')
                    continue

                title = translated.get('title')
                content = translated.get('content')
                if not isinstance(title, str) or not title.strip() or not isinstance(content, str) or not content.strip():
                    self.stderr.write(f'[{locale}] {doc.document_type}: пустой перевод, пропущен')
                    continue

                setattr(doc, f'title_{target_suffix}', title.strip())
                setattr(doc, f'content_{target_suffix}', content.strip())
                doc.save(update_fields=[f'title_{target_suffix}', f'content_{target_suffix}'])
                self.stdout.write(f'  [{locale}] {doc.document_type}: готово')

            self.stdout.write(self.style.SUCCESS(f'[{locale}] документов переведено: {len(jobs)}.'))
