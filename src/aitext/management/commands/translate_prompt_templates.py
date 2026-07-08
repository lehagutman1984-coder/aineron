# -*- coding: utf-8 -*-
"""
Заполняет английские переводы (title_en/content_en) для 34 встроенных
шаблонов промтов (PromptTemplate, user=None) — seed из миграции
0007_prompttemplate_seed.py. В отличие от translate_catalog (LLM через
laozhang), переводы здесь написаны вручную для контроля качества — это
конечный фиксированный набор из 34 промтов, не растущий каталог.

Несколько промтов адаптированы, а не переведены дословно, там где
оригинал был специфичен для русскоязычной аудитории (примеры соцсетей
VK, «адаптация под российского читателя», «русские/английские» стили
названий) — заменены на нейтральные международные аналоги.

Запуск: python manage.py translate_prompt_templates
По умолчанию не трогает уже заполненные *_en (чтобы не затереть правки
через админку). Полная перезапись: --force.
"""
from django.core.management.base import BaseCommand

from aitext.models import PromptTemplate

# title -> (title_en, content_en). Матчится по русскому title встроенных
# промтов (user=None) — если кто-то отредактирует ru-название через
# админку, просто перестанет находить совпадение и покажет предупреждение.
TRANSLATIONS = {
    # Код
    'Объясни код': ('Explain the code', 'Explain the following code line by line, describing what each part does:\n\n```\n[paste your code here]\n```'),
    'Найди баги': ('Find bugs', "Find all bugs, vulnerabilities, and issues in this code. For each one, specify the line, a description, and how to fix it:\n\n```\n[paste your code]\n```"),
    'Оптимизируй код': ('Optimize the code', 'Optimize this code for better performance. Show the original and optimized versions with an explanation:\n\n```\n[paste your code]\n```'),
    'Напиши тесты': ('Write tests', 'Write comprehensive unit tests for the following code. Cover the main cases and edge cases:\n\n```\n[paste your code]\n```'),
    'Code Review': ('Code Review', 'Do a detailed code review. Assess code quality, architecture, and readability, and give specific recommendations:\n\n```\n[paste your code]\n```'),
    'Конвертируй язык': ('Convert language', 'Convert this code from [source language] to [target language], preserving the logic and using idiomatic patterns:\n\n```\n[paste your code]\n```'),
    'Напиши функцию': ('Write a function', 'Write a Python function that [description]. Add a docstring, type hints, and error handling.'),
    'SQL запрос': ('SQL query', 'Write an SQL query for the following task. Use optimal indexes and joins:\n\nTask: [describe what you need to retrieve]\nTables: [list the tables and fields]'),
    'Регулярное выражение': ('Regular expression', 'Write a regular expression for [description]. Explain each part of the pattern and give example matches.'),
    'Объясни ошибку': ('Explain the error', 'Explain this error and how to fix it. List possible causes:\n\n```\n[paste the stack trace or error message]\n```'),

    # Перевод
    'На английский': ('To English', 'Translate the following text into English. Preserve the style, tone, and nuances of meaning:\n\n[paste your text]'),
    'На русский': ('To Russian', 'Translate the following text into Russian naturally and correctly, avoiding a literal word-for-word translation:\n\n[paste text here]'),
    'На немецкий': ('To German', 'Translate the following text into German:\n\n[paste your text]'),
    'Деловой перевод': ('Business translation', 'Translate this business document into English. Use a formal business style and professional terminology:\n\n[paste your document]'),
    'Адаптация текста': ('Localize text', "Adapt this text for an English-speaking audience: replace culturally specific references with equivalents your readers will recognize:\n\n[paste your text]"),
    'Упрости язык': ('Simplify language', 'Rewrite this text in simple, clear language. Replace complex words and phrasing with accessible alternatives while preserving the meaning:\n\n[paste your text]'),

    # Анализ
    'Резюме документа': ('Summarize a document', 'Write a concise summary of the following document: highlight the key ideas, conclusions, and important facts as a bulleted list:\n\n[paste your text]'),
    'SWOT анализ': ('SWOT analysis', 'Do a SWOT analysis (strengths, weaknesses, opportunities, threats) for:\n\n[describe the company / product / idea]'),
    'Сравни варианты': ('Compare options', 'Compare the following options against key criteria and give a well-reasoned recommendation:\n\nOption 1: [description]\nOption 2: [description]\n\nCriteria: [list them]'),
    'Анализ текста': ('Analyze text', 'Analyze this text: identify the tone, key arguments, logical fallacies, and strengths:\n\n[paste your text]'),
    'Анализ данных': ('Analyze data', 'Analyze this data, highlight key trends and anomalies, and provide an interpretation:\n\n[paste your data]'),
    'Разбор статьи': ('Break down an article', "Break down this article: summarize the gist, assess the source's credibility, and highlight what matters most:\n\n[paste the article text]"),

    # Письма
    'Деловое письмо': ('Business email', "Write a professional business email for the following situation. Use a formal tone:\n\nSituation: [describe]\nRecipient: [who it's for]\nGoal: [what you need to convey]"),
    'Ответ на жалобу': ('Reply to a complaint', 'Write a professional and diplomatic reply to a customer complaint. Acknowledge the issue, apologize, and offer a solution:\n\nComplaint: [complaint text]'),
    'Холодное письмо': ('Cold email', 'Write a compelling cold email to introduce yourself to a potential client. Keep it short, value-driven, with a clear call to action:\n\nProduct/service: [description]\nTarget client: [description]'),
    'Follow-up письмо': ('Follow-up email', 'Write a follow-up email after a meeting or call. Summarize what was discussed and outline the next steps:\n\nWhat was discussed: [brief summary]\nAgreements: [what was decided]'),
    'Коммерческое предложение': ('Sales proposal', 'Write a short and compelling sales proposal:\n\nProduct/service: [description]\nTarget client: [description]\nKey value: [what the client will get]'),

    # Учёба
    'Объясни концепцию': ('Explain a concept', 'Explain the concept of [topic] in simple terms, as if explaining it to a student. Use relatable analogies and real-life examples.'),
    'План обучения': ('Study plan', 'Create a detailed plan for learning [topic] from scratch in [timeframe]. Break it down by week, and include resources and practical exercises.'),
    'Шпаргалка': ('Cheat sheet', 'Create a concise cheat sheet on [topic]: key concepts, formulas, and rules — in a compact, easy-to-scan format.'),
    'Тест по теме': ('Quiz on a topic', 'Create 10 questions of varying difficulty to test knowledge of [topic]. For each question, give the correct answer and an explanation.'),
    'Список литературы': ('Reading list', "Recommend the best books, courses, and resources for learning [topic]. For each one, note the difficulty level and why it's worth choosing."),
    'Эссе': ('Essay', 'Help me write an essay on [topic]. Suggest a structure, key arguments, and a strong conclusion.\n\nLength: [word count]\nStyle: [academic / journalistic / free-form]'),

    # Творчество
    'Короткая история': ('Short story', 'Write an engaging short story (500-800 words) on the following theme:\n\n[describe the theme, genre, and main character]'),
    'Слоганы': ('Slogans', 'Come up with 10 memorable slogans for [product / company / campaign]. Vary the style: serious, playful, provocative.'),
    'Идеи для контента': ('Content ideas', 'Come up with 15 content ideas on [topic] for [platform]. Specify the format, angle, and why it will resonate with the audience.'),
    'Пост для соцсетей': ('Social media post', 'Write an engaging post for [Instagram / X / LinkedIn] about [topic]. Add a call to action:\n\nTone: [serious / friendly / expert]'),
    'Названия продукта': ('Product names', 'Come up with 15 name options for [product / service / company]. Show a range of styles: descriptive, invented words, and foreign-language-inspired.'),
    'Описание продукта': ('Product description', 'Write a compelling sales description for [product]. Highlight the key benefits and address objections:\n\nProduct: [description]\nTarget audience: [description]'),
}


class Command(BaseCommand):
    help = 'Заполняет title_en/content_en для встроенных шаблонов промтов (PromptTemplate, user=None)'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Перезаписать *_en, даже если уже заполнены')

    def handle(self, *args, **options):
        force = options['force']
        updated = 0
        skipped_filled = 0
        unmatched = []

        for obj in PromptTemplate.objects.filter(user__isnull=True):
            entry = TRANSLATIONS.get(obj.title_ru or obj.title)
            if entry is None:
                unmatched.append(obj.title)
                continue
            if not force and (obj.title_en or '').strip():
                skipped_filled += 1
                continue
            title_en, content_en = entry
            obj.title_en = title_en
            obj.content_en = content_en
            obj.save(update_fields=['title_en', 'content_en'])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f'Обновлено: {updated}, уже было заполнено: {skipped_filled}'))
        if unmatched:
            self.stdout.write(self.style.WARNING(f'Не найдено перевода для: {unmatched}'))
