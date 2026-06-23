from django.test import TestCase
from .commit_extract import parse_edit_blocks, apply_edit_blocks


class ParseEditBlocksTest(TestCase):
    """Sprint 8.1: тесты parse_edit_blocks()"""

    def test_single_block_single_hunk(self):
        text = (
            "=== EDIT: src/app.py ===\n"
            "<<<SEARCH>>>\n"
            "def hello():\n"
            "    return 1\n"
            "<<<REPLACE>>>\n"
            "def hello():\n"
            "    return 2\n"
            "<<<END>>>\n"
            "=== END EDIT ==="
        )
        result = parse_edit_blocks(text)
        self.assertEqual(list(result.keys()), ["src/app.py"])
        self.assertEqual(len(result["src/app.py"]), 1)
        self.assertEqual(result["src/app.py"][0]["search"], "def hello():\n    return 1\n")
        self.assertEqual(result["src/app.py"][0]["replace"], "def hello():\n    return 2\n")

    def test_single_block_multiple_hunks(self):
        text = (
            "=== EDIT: src/utils.py ===\n"
            "<<<SEARCH>>>\n"
            "x = 1\n"
            "<<<REPLACE>>>\n"
            "x = 10\n"
            "<<<END>>>\n"
            "<<<SEARCH>>>\n"
            "y = 2\n"
            "<<<REPLACE>>>\n"
            "y = 20\n"
            "<<<END>>>\n"
            "=== END EDIT ==="
        )
        result = parse_edit_blocks(text)
        self.assertEqual(list(result.keys()), ["src/utils.py"])
        self.assertEqual(len(result["src/utils.py"]), 2)
        self.assertEqual(result["src/utils.py"][0]["search"], "x = 1\n")
        self.assertEqual(result["src/utils.py"][1]["replace"], "y = 20\n")

    def test_multiple_files(self):
        text = (
            "=== EDIT: a.py ===\n"
            "<<<SEARCH>>>\n"
            "foo\n"
            "<<<REPLACE>>>\n"
            "bar\n"
            "<<<END>>>\n"
            "=== END EDIT ===\n"
            "Some prose in between.\n"
            "=== EDIT: b.py ===\n"
            "<<<SEARCH>>>\n"
            "baz\n"
            "<<<REPLACE>>>\n"
            "qux\n"
            "<<<END>>>\n"
            "=== END EDIT ==="
        )
        result = parse_edit_blocks(text)
        self.assertIn("a.py", result)
        self.assertIn("b.py", result)
        self.assertEqual(result["a.py"][0]["replace"], "bar\n")
        self.assertEqual(result["b.py"][0]["replace"], "qux\n")

    def test_no_edit_blocks_returns_empty(self):
        text = "Just some text without any edit blocks."
        result = parse_edit_blocks(text)
        self.assertEqual(result, {})

    def test_block_without_hunks_excluded(self):
        text = (
            "=== EDIT: empty.py ===\n"
            "No hunks here.\n"
            "=== END EDIT ==="
        )
        result = parse_edit_blocks(text)
        self.assertEqual(result, {})

    def test_leading_slash_stripped_from_path(self):
        text = (
            "=== EDIT: /src/app.py ===\n"
            "<<<SEARCH>>>\n"
            "a\n"
            "<<<REPLACE>>>\n"
            "b\n"
            "<<<END>>>\n"
            "=== END EDIT ==="
        )
        result = parse_edit_blocks(text)
        self.assertIn("src/app.py", result)
        self.assertNotIn("/src/app.py", result)

    def test_tolerant_marker_trailing_whitespace(self):
        """Маркеры с trailing whitespace должны парситься корректно."""
        text = (
            "=== EDIT: x.py ===\n"
            "<<<SEARCH>>>   \n"
            "alpha\n"
            "<<<REPLACE>>>  \n"
            "beta\n"
            "<<<END>>>\n"
            "=== END EDIT ==="
        )
        result = parse_edit_blocks(text)
        self.assertIn("x.py", result)
        self.assertEqual(result["x.py"][0]["search"], "alpha\n")
        self.assertEqual(result["x.py"][0]["replace"], "beta\n")

    def test_mixed_file_and_edit_blocks(self):
        """FILE и EDIT блоки в одном ответе — только EDIT парсится этой функцией."""
        text = (
            "=== FILE: main.py ===\n"
            "print('hello')\n"
            "=== END FILE ===\n"
            "=== EDIT: helper.py ===\n"
            "<<<SEARCH>>>\n"
            "old\n"
            "<<<REPLACE>>>\n"
            "new\n"
            "<<<END>>>\n"
            "=== END EDIT ==="
        )
        result = parse_edit_blocks(text)
        self.assertIn("helper.py", result)
        self.assertNotIn("main.py", result)

    def test_path_with_spaces_stripped(self):
        text = (
            "===  EDIT:   src/views.py   ===\n"
            "<<<SEARCH>>>\n"
            "pass\n"
            "<<<REPLACE>>>\n"
            "return None\n"
            "<<<END>>>\n"
            "=== END EDIT ==="
        )
        result = parse_edit_blocks(text)
        self.assertIn("src/views.py", result)


class ApplyEditBlocksTest(TestCase):
    """Sprint 8.1: тесты apply_edit_blocks()"""

    # ── exact match ────────────────────────────────────────────────────────────

    def test_exact_match_single_hunk(self):
        source = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
        hunks = [{"search": "    return 1\n", "replace": "    return 100\n"}]
        result = apply_edit_blocks(source, hunks)
        self.assertIn("return 100", result)
        self.assertIn("return 2", result)

    def test_exact_match_multiline_hunk(self):
        source = "class A:\n    def method(self):\n        x = 1\n        return x\n"
        hunks = [{"search": "    def method(self):\n        x = 1\n        return x\n",
                  "replace": "    def method(self):\n        x = 42\n        return x\n"}]
        result = apply_edit_blocks(source, hunks)
        self.assertIn("x = 42", result)
        self.assertNotIn("x = 1", result)

    def test_exact_match_preserves_rest_of_file(self):
        source = "line1\nline2\nline3\nline4\nline5\n"
        hunks = [{"search": "line3\n", "replace": "LINE_THREE\n"}]
        result = apply_edit_blocks(source, hunks)
        self.assertEqual(result, "line1\nline2\nLINE_THREE\nline4\nline5\n")

    def test_multiple_hunks_applied_in_order(self):
        source = "a = 1\nb = 2\nc = 3\n"
        hunks = [
            {"search": "a = 1\n", "replace": "a = 10\n"},
            {"search": "c = 3\n", "replace": "c = 30\n"},
        ]
        result = apply_edit_blocks(source, hunks)
        self.assertEqual(result, "a = 10\nb = 2\nc = 30\n")

    def test_replace_with_empty(self):
        """Замена текста на пустую строку (удаление блока)."""
        source = "keep_me\ndelete_me\nkeep_me_too\n"
        hunks = [{"search": "delete_me\n", "replace": ""}]
        result = apply_edit_blocks(source, hunks)
        self.assertNotIn("delete_me", result)
        self.assertIn("keep_me", result)

    def test_replace_at_file_start(self):
        source = "first_line\nsecond_line\n"
        hunks = [{"search": "first_line\n", "replace": "FIRST\n"}]
        result = apply_edit_blocks(source, hunks)
        self.assertTrue(result.startswith("FIRST\n"))

    def test_replace_at_file_end(self):
        source = "first_line\nlast_line\n"
        hunks = [{"search": "last_line\n", "replace": "LAST\n"}]
        result = apply_edit_blocks(source, hunks)
        self.assertIn("LAST", result)
        self.assertNotIn("last_line", result)

    # ── normalized line match ──────────────────────────────────────────────────

    def test_normalized_match_trailing_spaces(self):
        """Строки с trailing пробелами в файле — нормализованный поиск должен найти."""
        source = "def foo():   \n    return 1   \n"
        hunks = [{"search": "def foo():\n    return 1\n", "replace": "def foo():\n    return 99\n"}]
        result = apply_edit_blocks(source, hunks)
        self.assertIn("return 99", result)

    def test_normalized_match_mixed_trailing(self):
        """AI может выдать SEARCH без trailing пробелов, файл имеет trailing — должен найти."""
        source = "class Foo:  \n    pass  \n"
        hunks = [{"search": "class Foo:\n    pass\n", "replace": "class Foo:\n    x = 1\n"}]
        result = apply_edit_blocks(source, hunks)
        self.assertIn("x = 1", result)

    # ── uniqueness checks ──────────────────────────────────────────────────────

    def test_exact_match_not_unique_raises(self):
        """Два вхождения SEARCH в файле — должна быть ошибка, не тихий патч."""
        source = "x = 1\nfoo\nx = 1\n"
        hunks = [{"search": "x = 1\n", "replace": "x = 99\n"}]
        with self.assertRaises(ValueError) as ctx:
            apply_edit_blocks(source, hunks)
        self.assertIn("не уникален", str(ctx.exception))

    def test_normalized_not_unique_raises(self):
        """Два нормализованных вхождения — ошибка."""
        source = "foo  \nbar\nfoo  \n"
        hunks = [{"search": "foo\n", "replace": "baz\n"}]
        with self.assertRaises(ValueError) as ctx:
            apply_edit_blocks(source, hunks)
        self.assertIn("не уникален", str(ctx.exception))

    def test_search_not_found_raises(self):
        source = "hello world\n"
        hunks = [{"search": "nonexistent text\n", "replace": "something\n"}]
        with self.assertRaises(ValueError) as ctx:
            apply_edit_blocks(source, hunks)
        self.assertIn("не найден", str(ctx.exception))

    def test_empty_search_raises(self):
        source = "some code\n"
        hunks = [{"search": "", "replace": "replacement\n"}]
        with self.assertRaises(ValueError) as ctx:
            apply_edit_blocks(source, hunks)
        self.assertIn("пустой", str(ctx.exception))

    def test_whitespace_only_search_raises(self):
        source = "some code\n"
        hunks = [{"search": "   \n   \n", "replace": "replacement\n"}]
        with self.assertRaises(ValueError) as ctx:
            apply_edit_blocks(source, hunks)
        self.assertIn("пустой", str(ctx.exception))

    # ── edge cases ─────────────────────────────────────────────────────────────

    def test_empty_hunks_list_returns_source(self):
        source = "unchanged content\n"
        result = apply_edit_blocks(source, [])
        self.assertEqual(result, source)

    def test_second_hunk_uses_result_of_first(self):
        """Второй хунк применяется к уже изменённому тексту от первого."""
        source = "a\nb\nc\n"
        hunks = [
            {"search": "a\n", "replace": "A\n"},
            {"search": "A\nb\n", "replace": "AB\n"},
        ]
        result = apply_edit_blocks(source, hunks)
        self.assertEqual(result, "AB\nc\n")

    def test_real_world_python_function(self):
        source = (
            "import os\n"
            "\n"
            "LIMIT = 100\n"
            "\n"
            "def get_limit():\n"
            "    return LIMIT\n"
            "\n"
            "def process(n):\n"
            "    if n > LIMIT:\n"
            "        raise ValueError('too big')\n"
            "    return n * 2\n"
        )
        hunks = [
            {
                "search": "LIMIT = 100\n",
                "replace": "LIMIT = 200\n",
            },
            {
                "search": "    if n > LIMIT:\n        raise ValueError('too big')\n",
                "replace": "    if n > LIMIT:\n        raise ValueError(f'too big: {n}')\n",
            },
        ]
        result = apply_edit_blocks(source, hunks)
        self.assertIn("LIMIT = 200", result)
        self.assertIn("f'too big: {n}'", result)
        self.assertNotIn("LIMIT = 100", result)
        self.assertNotIn("'too big'", result)

    def test_no_change_when_replace_equals_search(self):
        source = "const x = 1;\n"
        hunks = [{"search": "const x = 1;\n", "replace": "const x = 1;\n"}]
        result = apply_edit_blocks(source, hunks)
        self.assertEqual(result, source)

    def test_hunk_error_number_in_message(self):
        """Номер хунка в сообщении об ошибке для отладки."""
        source = "line\n"
        hunks = [
            {"search": "line\n", "replace": "line\n"},
            {"search": "missing\n", "replace": "x\n"},
        ]
        with self.assertRaises(ValueError) as ctx:
            apply_edit_blocks(source, hunks)
        self.assertIn("#2", str(ctx.exception))
