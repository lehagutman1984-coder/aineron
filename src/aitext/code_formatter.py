import re
import html
import logging
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer, ClassNotFound, TextLexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound as UtilClassNotFound

logger = logging.getLogger(__name__)


class CodeFormatter:
    """Класс для форматирования кода с подсветкой синтаксиса с полной поддержкой Pygments"""

    def __init__(self):
        self._initialize_language_cache()

    @classmethod
    def _initialize_language_cache(cls):
        if hasattr(cls, '_LANGUAGE_CACHE_INITIALIZED'):
            return

        cls._LANGUAGE_CACHE_INITIALIZED = True

        from pygments.lexers import get_all_lexers
        all_lexers = list(get_all_lexers())

        language_mapping = {}
        display_names = {}

        for lexer_name, aliases, _, mimetypes in all_lexers:
            if not aliases:
                continue

            main_alias = aliases[0]

            for alias in aliases:
                language_mapping[alias.lower()] = main_alias

            display_name = cls._generate_display_name(lexer_name, main_alias)
            display_names[main_alias] = display_name

            for alias in aliases:
                display_names[alias.lower()] = display_name

        file_extensions = {
            'py': 'python', 'js': 'javascript', 'ts': 'typescript', 'java': 'java',
            'c': 'c', 'cpp': 'cpp', 'cs': 'csharp', 'go': 'go', 'rs': 'rust',
            'php': 'php', 'rb': 'ruby', 'swift': 'swift', 'kt': 'kotlin',
            'html': 'html', 'css': 'css', 'sql': 'sql', 'sh': 'bash', 'json': 'json',
            'xml': 'xml', 'yaml': 'yaml', 'md': 'markdown', 'dockerfile': 'dockerfile',
        }
        for ext, lang in file_extensions.items():
            if lang in language_mapping:
                language_mapping[ext] = language_mapping[lang]

        cls.LANGUAGE_ALIASES = language_mapping
        cls.LANGUAGE_DISPLAY_NAMES = display_names
        cls._ALL_LANGUAGES = sorted(set(language_mapping.values()))

    @classmethod
    def _generate_display_name(cls, lexer_name: str, main_alias: str) -> str:
        special_cases = {
            'csharp': 'C#', 'cpp': 'C++', 'python': 'Python', 'javascript': 'JavaScript',
            'typescript': 'TypeScript', 'html': 'HTML', 'css': 'CSS', 'sql': 'SQL',
            'bash': 'Bash', 'json': 'JSON', 'xml': 'XML', 'yaml': 'YAML', 'markdown': 'Markdown'
        }
        if main_alias in special_cases:
            return special_cases[main_alias]
        return main_alias.capitalize()

    @classmethod
    def detect_language(cls, code: str, language_hint: str = None) -> str:
        cls._initialize_language_cache()
        if language_hint:
            hint_lower = language_hint.lower().strip()
            if hint_lower in cls.LANGUAGE_ALIASES:
                return cls.LANGUAGE_ALIASES[hint_lower]
            try:
                lexer = get_lexer_by_name(hint_lower)
                return lexer.aliases[0] if lexer.aliases else 'text'
            except (ClassNotFound, UtilClassNotFound):
                pass
        try:
            sample = code[:3000]
            lexer = guess_lexer(sample)
            if lexer.aliases:
                main_alias = lexer.aliases[0]
                return cls.LANGUAGE_ALIASES.get(main_alias, main_alias)
            return 'text'
        except Exception:
            return 'text'

    @classmethod
    def format_code_block(cls, code: str, language: str = None) -> str:
        cls._initialize_language_cache()
        code = code.strip()
        if not code:
            return ""

        detected_language = cls.detect_language(code, language)

        try:
            if detected_language == 'text':
                lexer = TextLexer()
            else:
                lexer = get_lexer_by_name(detected_language)
            formatter = HtmlFormatter(style='friendly', linenos=False, cssclass='', noclasses=True, nowrap=True)
            highlighted_code = highlight(code, lexer, formatter)

            display_name = cls.LANGUAGE_DISPLAY_NAMES.get(detected_language, detected_language.capitalize())

            return f'''
<div class="code-block">
    <div class="code-header">
        <span class="code-language">{display_name}</span>
        <div class="code-actions">
            <button class="code-action-btn copy-code">
                <i class="far fa-copy"></i>
                Копировать
            </button>
            <button class="code-action-btn download-code">
                <i class="fas fa-download"></i>
                Скачать
            </button>
        </div>
    </div>
    <div class="code-content">
        <pre><code class="language-{detected_language}">{highlighted_code}</code></pre>
    </div>
</div>
'''
        except Exception as e:
            logger.error(f"Error highlighting code: {e}")
            escaped_code = html.escape(code)
            display_name = cls.LANGUAGE_DISPLAY_NAMES.get(detected_language, detected_language.capitalize())
            return f'''
<div class="code-block">
    <div class="code-header">
        <span class="code-language">{display_name}</span>
        <div class="code-actions">
            <button class="code-action-btn copy-code">
                <i class="far fa-copy"></i>
                Копировать
            </button>
            <button class="code-action-btn download-code">
                <i class="fas fa-download"></i>
                Скачать
            </button>
        </div>
    </div>
    <div class="code-content">
        <pre><code>{escaped_code}</code></pre>
    </div>
</div>
'''

    @classmethod
    def _format_inline_markdown(cls, text: str) -> str:
        if not text:
            return ""
        # Зачёркнутый текст (двойные тильды)
        text = re.sub(r'~~(.*?)~~', r'<del>\1</del>', text)
        # Жирный и курсив одновременно ***текст***
        text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        # Жирный **текст** или __текст__
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.*?)__', r'<strong>\1</strong>', text)
        # Курсив *текст* или _текст_
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        text = re.sub(r'_(.*?)_', r'<em>\1</em>', text)
        # Inline код `код`
        text = re.sub(r'`([^`]+)`', r'<code class="inline-code">\1</code>', text)
        # Ссылки [текст](url)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" class="ai-link" target="_blank" rel="noopener noreferrer">\1</a>', text)
        return text

    @classmethod
    def _markdown_table_to_html(cls, markdown_table: str) -> str:
        try:
            lines = [line.strip() for line in markdown_table.strip().split('\n') if line.strip()]
            if len(lines) < 2:
                return markdown_table
            headers_line = lines[0]
            if headers_line.startswith('|') and headers_line.endswith('|'):
                headers = [cell.strip() for cell in headers_line[1:-1].split('|')]
            else:
                return markdown_table
            headers = [h for h in headers if h]
            num_columns = len(headers)
            data_rows = []
            for line in lines[2:]:
                if line.startswith('|') and line.endswith('|'):
                    cells = [cell.strip() for cell in line[1:-1].split('|')]
                    if len(cells) < num_columns:
                        cells.extend([''] * (num_columns - len(cells)))
                    elif len(cells) > num_columns:
                        cells = cells[:num_columns]
                    data_rows.append(cells)
            if not headers and data_rows:
                max_cols = max(len(row) for row in data_rows) if data_rows else 1
                headers = [f"Столбец {i+1}" for i in range(max_cols)]
                num_columns = max_cols
            normalized_rows = []
            for row in data_rows:
                if len(row) < num_columns:
                    row += [''] * (num_columns - len(row))
                else:
                    row = row[:num_columns]
                normalized_rows.append(row)
            html_rows = ['<div class="ai-table-container"><div class="ai-table-wrapper"><table class="ai-table">', '<thead><tr>']
            for header in headers:
                html_rows.append(f'<th>{cls._format_inline_markdown(header)}</th>')
            html_rows.append('</thead><tbody>')
            for row in normalized_rows:
                if any(cell.strip() for cell in row):
                    html_rows.append('<tr>')
                    for cell in row:
                        html_rows.append(f'<td>{cls._format_inline_markdown(cell)}</td>')
                    html_rows.append('</tr>')
            html_rows.append('</tbody></table></div></div>')
            return '\n'.join(html_rows)
        except Exception as e:
            logger.error(f"Table conversion error: {e}")
            return f'<pre class="ai-table-error"><code>{html.escape(markdown_table)}</code></pre>'

    @classmethod
    def format_ai_response(cls, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\n{3,}', '\n\n', text.strip())

        # Extract tables
        table_pattern = r'(\|[^\n]+\|\r?\n\|[ \-\|:]+\|\r?\n(?:\|[^\n]+\|\r?\n?)*)'
        table_blocks = []
        def extract_table(match):
            table_md = match.group(1).strip()
            table_html = cls._markdown_table_to_html(table_md)
            idx = len(table_blocks)
            table_blocks.append(table_html)
            return f'__TABLE_BLOCK_{idx}__'
        text_with_placeholders = re.sub(table_pattern, extract_table, text, flags=re.MULTILINE)

        # Extract code blocks
        code_pattern = r'```(\w+)?\n([\s\S]*?)(?:\n```|$)'
        code_blocks = []
        def extract_code(match):
            lang = match.group(1) or ''
            code = match.group(2).rstrip()
            formatted = cls.format_code_block(code, lang)
            idx = len(code_blocks)
            code_blocks.append(formatted)
            return f'__CODE_BLOCK_{idx}__'
        text_with_placeholders = re.sub(code_pattern, extract_code, text_with_placeholders, flags=re.DOTALL)

        # Headers
        for i in range(1, 7):
            text_with_placeholders = re.sub(r'^#{' + str(i) + r'} (.+)$', f'<h{i} class="ai-heading ai-heading-{i}">\\1</h{i}>', text_with_placeholders, flags=re.MULTILINE)

        # Ordered lists
        def format_ordered(m):
            lines = m.group(0).strip().split('\n')
            html_lines = ['<ol class="ai-ordered-list">']
            for line in lines:
                if re.match(r'^\d+\.\s+', line):
                    item = re.sub(r'^\d+\.\s+', '', line)
                    html_lines.append(f'<li class="ai-list-item">{cls._format_inline_markdown(item)}</li>')
                else:
                    html_lines.append(f'<span class="ai-list-continuation">{cls._format_inline_markdown(line)}</span>')
            html_lines.append('</ol>')
            return '\n'.join(html_lines)
        text_with_placeholders = re.sub(r'(?:(?:^\d+\.\s+.+(?:\n(?!^\d+\.\s+).+)*)+)', format_ordered, text_with_placeholders, flags=re.MULTILINE)

        # Unordered lists
        def format_unordered(m):
            lines = m.group(0).strip().split('\n')
            html_lines = ['<ul class="ai-unordered-list">']
            for line in lines:
                if re.match(r'^[\*\+\-]\s+', line):
                    item = re.sub(r'^[\*\+\-]\s+', '', line)
                    html_lines.append(f'<li class="ai-list-item">{cls._format_inline_markdown(item)}</li>')
                else:
                    html_lines.append(f'<span class="ai-list-continuation">{cls._format_inline_markdown(line)}</span>')
            html_lines.append('</ul>')
            return '\n'.join(html_lines)
        text_with_placeholders = re.sub(r'(?:(?:^[\*\+\-]\s+.+(?:\n(?!^[\*\+\-]\s+).+)*)+)', format_unordered, text_with_placeholders, flags=re.MULTILINE)

        # Horizontal rules
        text_with_placeholders = re.sub(r'^\s*([\-\*_]{3,})\s*$', r'<hr class="ai-horizontal-line">', text_with_placeholders, flags=re.MULTILINE)

        # Inline code (after lists)
        text_with_placeholders = re.sub(r'`([^`]+)`', r'<code class="inline-code">\1</code>', text_with_placeholders)

        # Split into paragraphs and restore blocks
        paragraphs = re.split(r'\n\s*\n+', text_with_placeholders)
        final_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            for i, table in enumerate(table_blocks):
                para = para.replace(f'__TABLE_BLOCK_{i}__', table)
            for i, code in enumerate(code_blocks):
                para = para.replace(f'__CODE_BLOCK_{i}__', code)
            if re.match(r'^<(h[1-6]|ul|ol|hr|table|div)', para) or '<div class="ai-table' in para or '<div class="code-block' in para:
                final_paragraphs.append(para)
            else:
                formatted_para = cls._format_inline_markdown(para)
                if formatted_para.strip():
                    final_paragraphs.append(f'<p>{formatted_para}</p>')
        import re as _re
        result = '\n'.join(final_paragraphs)
        # Wrap citation refs [1], [2], etc. in hoverable spans (skip markdown links [N](url))
        result = _re.sub(
            r'\[(\d+)\](?!\()',
            r'<span class="cite-ref" data-cite="\1">[\1]</span>',
            result
        )
        return result