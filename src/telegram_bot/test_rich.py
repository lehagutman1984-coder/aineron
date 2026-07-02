"""Юнит-тесты конвертера rich.py (S1). Без Django: python -m unittest telegram_bot.test_rich"""
import unittest

from telegram_bot.rich import (
    md_to_rich_blocks, blocks_to_payload, extract_first_code,
)


class MdToRichBlocksTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(md_to_rich_blocks(''), [])
        self.assertEqual(md_to_rich_blocks('   \n  '), [])

    def test_plain_paragraph(self):
        blocks = md_to_rich_blocks('Просто текст ответа.')
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].type, 'paragraph')
        self.assertEqual(blocks[0].text, 'Просто текст ответа.')

    def test_two_paragraphs(self):
        blocks = md_to_rich_blocks('Первый абзац.\n\nВторой абзац.')
        self.assertEqual([b.type for b in blocks], ['paragraph', 'paragraph'])

    def test_heading(self):
        blocks = md_to_rich_blocks('## Заголовок\nтекст')
        self.assertEqual(blocks[0].type, 'heading')
        self.assertEqual(blocks[0].level, 2)
        self.assertEqual(blocks[0].text, 'Заголовок')
        self.assertEqual(blocks[1].type, 'paragraph')

    def test_heading_level_capped_at_3(self):
        blocks = md_to_rich_blocks('###### мелкий')
        self.assertEqual(blocks[0].level, 3)

    def test_code_block(self):
        blocks = md_to_rich_blocks('До\n```python\nprint(1)\n```\nПосле')
        types = [b.type for b in blocks]
        self.assertEqual(types, ['paragraph', 'preformatted', 'paragraph'])
        self.assertEqual(blocks[1].language, 'python')
        self.assertEqual(blocks[1].text, 'print(1)')

    def test_code_block_no_lang(self):
        blocks = md_to_rich_blocks('```\nx = 1\n```')
        self.assertEqual(blocks[0].type, 'preformatted')
        self.assertEqual(blocks[0].language, '')

    def test_table(self):
        md = '| Модель | Цена |\n|---|---|\n| GPT-5 | 4 ₽ |\n| Claude | 3 ₽ |'
        blocks = md_to_rich_blocks(md)
        self.assertEqual(len(blocks), 1)
        t = blocks[0]
        self.assertEqual(t.type, 'table')
        self.assertEqual(t.header, ['Модель', 'Цена'])
        self.assertEqual(t.rows, [['GPT-5', '4 ₽'], ['Claude', '3 ₽']])

    def test_table_with_alignment(self):
        md = '| a | b |\n|:---|---:|\n| 1 | 2 |'
        blocks = md_to_rich_blocks(md)
        self.assertEqual(blocks[0].type, 'table')
        self.assertEqual(blocks[0].rows, [['1', '2']])

    def test_pipe_in_text_not_table(self):
        blocks = md_to_rich_blocks('a | b без разделителя')
        self.assertEqual(blocks[0].type, 'paragraph')

    def test_math(self):
        blocks = md_to_rich_blocks('Формула: $$E = mc^2$$ готово')
        types = [b.type for b in blocks]
        self.assertIn('math', types)
        math = [b for b in blocks if b.type == 'math'][0]
        self.assertEqual(math.text, 'E = mc^2')

    def test_thinking(self):
        blocks = md_to_rich_blocks('<think>Рассуждаю о задаче</think>Ответ: 42')
        self.assertEqual(blocks[0].type, 'thinking')
        self.assertEqual(blocks[0].text, 'Рассуждаю о задаче')
        self.assertEqual(blocks[1].type, 'paragraph')
        self.assertEqual(blocks[1].text, 'Ответ: 42')

    def test_thinking_tag_variant(self):
        blocks = md_to_rich_blocks('<thinking>мысль</thinking>ок')
        self.assertEqual(blocks[0].type, 'thinking')

    def test_bullet_list(self):
        blocks = md_to_rich_blocks('- один\n- два\n- три')
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].type, 'list')
        self.assertFalse(blocks[0].ordered)
        self.assertEqual(blocks[0].items, ['один', 'два', 'три'])

    def test_ordered_list(self):
        blocks = md_to_rich_blocks('1. раз\n2. два')
        self.assertTrue(blocks[0].ordered)
        self.assertEqual(blocks[0].items, ['раз', 'два'])

    def test_mixed_document(self):
        md = (
            '## Отчёт\n\nВводный текст.\n\n'
            '| k | v |\n|---|---|\n| a | 1 |\n\n'
            '```js\nlet x = 1\n```\n\n- пункт'
        )
        types = [b.type for b in md_to_rich_blocks(md)]
        self.assertEqual(types, ['heading', 'paragraph', 'table', 'preformatted', 'list'])

    def test_code_inside_not_parsed_as_table(self):
        md = '```\n| not | table |\n|---|---|\n```'
        blocks = md_to_rich_blocks(md)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].type, 'preformatted')

    def test_payload_serialization(self):
        md = '## H\n\n| a |\n|---|\n| 1 |\n\n$$x$$'
        payload = blocks_to_payload(md_to_rich_blocks(md))
        self.assertEqual(payload[0], {'type': 'heading', 'level': 2, 'text': 'H'})
        self.assertEqual(payload[1]['type'], 'table')
        self.assertEqual(payload[2], {'type': 'math', 'expression': 'x'})


class ExtractFirstCodeTest(unittest.TestCase):
    def test_code_block(self):
        self.assertEqual(extract_first_code('текст ```py\nx=1\n``` конец'), 'x=1')

    def test_inline_code(self):
        self.assertEqual(extract_first_code('запусти `npm install` сейчас'), 'npm install')

    def test_too_long_skipped(self):
        code = 'x' * 300
        self.assertEqual(extract_first_code(f'```\n{code}\n```'), '')

    def test_no_code(self):
        self.assertEqual(extract_first_code('просто текст'), '')

    def test_empty(self):
        self.assertEqual(extract_first_code(''), '')


if __name__ == '__main__':
    unittest.main()
