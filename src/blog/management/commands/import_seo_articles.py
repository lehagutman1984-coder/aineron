"""
Импорт нативно вычитанных SEO-статей id/ar обратно в Post (SEO_PILOT_ID_AR_PLAN.md, шаг 6.5).

generate_seo_articles.py создал черновики (is_published=False) с content в виде
HTML. Для нативной вычитки текст был выгружен в плоский текстовый формат
(N. SLUG: ... / ЗАГОЛОВОК: / КРАТКОЕ ОПИСАНИЕ: / ТЕКСТ СТАТЬИ: / ЧАСТО
ЗАДАВАЕМЫЕ ВОПРОСЫ:) — HTML-теги при этом были потеряны. Эта команда парсит
вычитанный текст и детерминированно восстанавливает HTML (без повторного
прогона через LLM — иначе результат носителя мог бы измениться незаметно).

Разбивка на h2/h3 не восстановима (потеряна при выгрузке в плоский текст) —
все заголовки становятся <h2>, это не критично для SEO.

Обновляет только slug/title/preview_text/content/faq_items на СУЩЕСТВУЮЩЕЙ
записи Post (созданной generate_seo_articles.py на сервере) — category и
neural_networks не трогает. is_published не меняет, если явно не передан
--publish (публикация должна идти по одной статье, см. план шаг 6.5).

Запуск:
  python manage.py import_seo_articles "aineron_ar_articles (Done).txt" --lang=ar --dry-run
  python manage.py import_seo_articles "aineron_ar_articles (Done).txt" --lang=ar --apply
  python manage.py import_seo_articles "aineron_ar_articles (Done).txt" --lang=ar --apply --publish=slug-one,slug-two
"""
import re

from django.core.management.base import BaseCommand, CommandError

_ARTICLE_RE = re.compile(
    r'={5,}\s*\n\d+\.\s*SLUG:\s*(?P<slug>[\w-]+)\s*\n={5,}\s*\n'
    r'(?P<body>.*?)'
    r'(?=\n={5,}\s*\n\d+\.\s*SLUG:|\Z)',
    re.DOTALL,
)

_FIELD_LABELS = ['ЗАГОЛОВОК', 'КРАТКОЕ ОПИСАНИЕ', 'ТЕКСТ СТАТЬИ', 'ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ']
_FIELD_RE = re.compile(
    r'^(' + '|'.join(re.escape(l) for l in _FIELD_LABELS) + r'):\s*$',
    re.MULTILINE,
)

# FAQ Q/A построчные префиксы — разные по языку/партии экспорта. ar/id
# экспортировались с префиксом на целевом языке; fa/tr — более поздняя
# партия экспорта, использует язык-агностичные кириллические маркеры
# (В=Вопрос, О=Ответ), чтобы не зависеть от письменности целевого языка.
FAQ_PREFIXES = {
    'ar': ('س', 'ج'),
    'id': ('T', 'J'),
    'fa': ('В', 'О'),
    'tr': ('В', 'О'),
}

_HTML_ESCAPE = {'&': '&amp;', '<': '&lt;', '>': '&gt;'}


def _esc(text):
    for ch, rep in _HTML_ESCAPE.items():
        text = text.replace(ch, rep)
    return text


def _split_fields(body):
    matches = list(_FIELD_RE.finditer(body))
    if not matches:
        raise ValueError('не найдено ни одной метки поля (ЗАГОЛОВОК/КРАТКОЕ ОПИСАНИЕ/...)')
    fields = {}
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        fields[name] = body[start:end].strip()
    return fields


def _is_heading(line):
    """Заголовок — короткая однострочная реплика, не завершённая как обычное
    предложение (не оканчивается точкой/двоеточием/запятой)."""
    if len(line) > 100:
        return False
    return not line.rstrip().endswith(('.', ':', '،', '،', ';', '؛', ','))


def article_text_to_html(text):
    """Детерминированно оборачивает вычитанный плоский текст в semantic HTML,
    не меняя ни одного символа исходных предложений."""
    blocks = re.split(r'\n\s*\n', text.strip())
    html_parts = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) == 1:
            line = lines[0]
            if _is_heading(line):
                html_parts.append(f'<h2>{_esc(line)}</h2>')
            else:
                html_parts.append(f'<p>{_esc(line)}</p>')
        else:
            first, rest = lines[0], lines[1:]
            if first.endswith((':', '،', '.')) and len(first) <= 90:
                desc = ' '.join(rest)
                html_parts.append(f'<p><strong>{_esc(first)}</strong> {_esc(desc)}</p>')
            else:
                html_parts.append(f'<p>{_esc(" ".join(lines))}</p>')
    return '\n'.join(html_parts)


def parse_faq(text, lang):
    if lang not in FAQ_PREFIXES:
        raise ValueError(f'нет известного FAQ-префикса для языка {lang!r}')
    q_pref, a_pref = FAQ_PREFIXES[lang]
    pattern = re.compile(
        rf'^{re.escape(q_pref)}:\s*(?P<q>.+?)\s*\n{re.escape(a_pref)}:\s*(?P<a>.+?)'
        rf'(?=\n{re.escape(q_pref)}:|\Z)',
        re.DOTALL | re.MULTILINE,
    )
    items = []
    for m in pattern.finditer(text.strip()):
        question = ' '.join(m.group('q').split())
        answer = ' '.join(m.group('a').split())
        # найденный в проверке баг вычитки: ответ иногда начинается с
        # задвоенного префикса ("ج: ج: ...") — снимаем его при импорте.
        dup_prefix = f'{a_pref}:'
        while answer.startswith(dup_prefix):
            answer = answer[len(dup_prefix):].strip()
        items.append({'question': question, 'answer': answer})
    return items


def parse_articles_file(path, lang):
    raw = open(path, encoding='utf-8').read()
    matches = list(_ARTICLE_RE.finditer(raw))
    if not matches:
        raise ValueError(f'{path}: не найдено ни одного блока "N. SLUG: ..."')
    articles = []
    for m in matches:
        slug = m.group('slug')
        try:
            fields = _split_fields(m.group('body'))
            missing = [l for l in _FIELD_LABELS if l not in fields]
            if missing:
                raise ValueError(f'отсутствуют поля {missing}')
            title = fields['ЗАГОЛОВОК']
            preview_text = fields['КРАТКОЕ ОПИСАНИЕ']
            content_html = article_text_to_html(fields['ТЕКСТ СТАТЬИ'])
            faq_items = parse_faq(fields['ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ'], lang)
            if not faq_items:
                raise ValueError('faq_items пуст после парсинга — проверь FAQ-префиксы')
        except ValueError as e:
            raise ValueError(f'{path}: slug={slug}: {e}') from e
        articles.append({
            'slug': slug,
            'title': title,
            'preview_text': preview_text[:300],
            'content': content_html,
            'faq_items': faq_items,
        })
    return articles


class Command(BaseCommand):
    help = 'Импортирует нативно вычитанные id/ar SEO-статьи из плоского текста обратно в Post'

    def add_arguments(self, parser):
        parser.add_argument('path', help='Путь к файлу вида "aineron_ar_articles (Done).txt"')
        parser.add_argument('--lang', required=True, choices=list(FAQ_PREFIXES), help='Язык статей в файле')
        parser.add_argument('--apply', action='store_true', help='Записать в БД (по умолчанию — только парсинг и предпросмотр)')
        parser.add_argument('--publish', default='', help='Список slug через запятую, которым выставить is_published=True (требует --apply)')

    def handle(self, *args, **options):
        path = options['path']
        lang = options['lang']
        apply_ = options['apply']
        publish_slugs = {s.strip() for s in options['publish'].split(',') if s.strip()}
        if publish_slugs and not apply_:
            raise CommandError('--publish требует --apply')

        articles = parse_articles_file(path, lang)
        self.stdout.write(f'{path}: распарсено {len(articles)} статей ({lang})')

        for a in articles:
            self.stdout.write(f"\n--- {a['slug']} ---")
            self.stdout.write(f"title: {a['title']}")
            self.stdout.write(f"preview_text: {a['preview_text'][:120]}...")
            self.stdout.write(f"content: {len(a['content'])} chars, {a['content'].count('<h2>')} h2, {a['content'].count('<p>')} p")
            self.stdout.write(f"faq_items: {len(a['faq_items'])}")

        if not apply_:
            self.stdout.write(self.style.WARNING('\n--dry-run (по умолчанию): в БД ничего не записано. Запусти с --apply для записи.'))
            return

        from blog.models import Post

        for a in articles:
            try:
                post = Post.objects.get(slug=a['slug'], language=lang)
            except Post.DoesNotExist:
                self.stderr.write(self.style.ERROR(
                    f"  {a['slug']} — Post с language={lang} не найден. Ожидался черновик от generate_seo_articles.py. Пропуск."
                ))
                continue

            post.title = a['title']
            post.preview_text = a['preview_text']
            post.content = a['content']
            post.faq_items = a['faq_items']
            if a['slug'] in publish_slugs:
                post.is_published = True
            post.save(update_fields=['title', 'preview_text', 'content', 'faq_items', 'is_published', 'updated_at'])
            self.stdout.write(self.style.SUCCESS(
                f"  {a['slug']} — обновлён"
                f"{' и опубликован' if a['slug'] in publish_slugs else ' (is_published не менялся)'}"
            ))

        not_found_publish = publish_slugs - {a['slug'] for a in articles}
        if not_found_publish:
            self.stderr.write(self.style.WARNING(f'--publish содержит slug, которых нет в файле: {not_found_publish}'))
