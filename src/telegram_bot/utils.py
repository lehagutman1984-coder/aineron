import re
import html


# Символы, требующие экранирования в MarkdownV2
_MD_SPECIAL = r'\_*[]()~`>#+-=|{}.!'

DIVIDER = '─' * 21


def card(title: str, body: str, footer: str = '') -> str:
    """Build a visual card: bold title + divider + body [+ divider + footer]."""
    parts = [f'<b>{title}</b>', DIVIDER, body]
    if footer:
        parts += [DIVIDER, footer]
    return '\n'.join(parts)


def telegram_format(text: str) -> str:
    """
    Конвертирует markdown-текст из AI в HTML для Telegram (parse_mode=HTML).
    HTML безопаснее MarkdownV2 — не требует экранирования спецсимволов в тексте.
    """
    if not text:
        return text

    # Код-блоки: ```lang\n...\n``` → <pre><code>...</code></pre>
    def replace_code_block(m):
        code = html.escape(m.group(2))
        lang = m.group(1).strip() if m.group(1) else ''
        return f'<pre><code class="language-{lang}">{code}</code></pre>' if lang else f'<pre>{code}</pre>'

    text = re.sub(r'```(\w*)\n?(.*?)```', replace_code_block, text, flags=re.DOTALL)

    # Инлайн-код: `code` → <code>code</code>
    def replace_inline_code(m):
        return f'<code>{html.escape(m.group(1))}</code>'

    text = re.sub(r'`([^`\n]+)`', replace_inline_code, text)

    # Таблицы → убираем разделительные строки, оставляем текст
    lines = text.split('\n')
    filtered = []
    for line in lines:
        if re.match(r'^\s*\|[-:| ]+\|\s*$', line):
            continue
        filtered.append(line)
    text = '\n'.join(filtered)

    # **bold** → <b>bold</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # *italic* → <i>italic</i>  (не трогаем одиночные звёздочки в тексте)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    # __underline__ → <u>...</u>
    text = re.sub(r'__(.+?)__', r'<u>\1</u>', text)

    return text


def split_message(text: str, limit: int = 4096) -> list:
    """Разбить длинное сообщение по границам абзацев."""
    if len(text) <= limit:
        return [text]

    parts = []
    current = ''
    for paragraph in text.split('\n\n'):
        if len(current) + len(paragraph) + 2 > limit:
            if current:
                parts.append(current.strip())
            current = paragraph
        else:
            current = (current + '\n\n' + paragraph).lstrip('\n')

    if current:
        parts.append(current.strip())
    return parts or [text[:limit]]


def stars_estimate(balance: int, cost_per_message: int) -> int:
    if cost_per_message == 0:
        return 0
    return balance // cost_per_message
