"""Юнит-тесты движка Agent Mode (S9). Без Django: python -m unittest telegram_bot.test_agent"""
import unittest

from telegram_bot.agent import safe_calc, parse_action, step_human


class SafeCalcTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(safe_calc('2 + 2 * 2'), '6')
        self.assertEqual(safe_calc('(100 - 20) / 4'), '20.0')
        self.assertEqual(safe_calc('2 ** 10'), '1024')

    def test_functions(self):
        self.assertEqual(safe_calc('round(10 / 3, 2)'), '3.33')
        self.assertEqual(safe_calc('max(1, 5, 3)'), '5')
        self.assertEqual(safe_calc('abs(-7)'), '7')

    def test_unary(self):
        self.assertEqual(safe_calc('-5 + 3'), '-2')

    def test_division_by_zero(self):
        self.assertIn('деление на ноль', safe_calc('1 / 0'))

    def test_no_code_execution(self):
        self.assertIn('Ошибка', safe_calc('__import__("os").system("id")'))
        self.assertIn('Ошибка', safe_calc('open("/etc/passwd")'))
        self.assertIn('Ошибка', safe_calc('"a" * 1000000'))

    def test_huge_power_blocked(self):
        self.assertIn('Ошибка', safe_calc('9 ** 999999'))

    def test_empty_and_too_long(self):
        self.assertIn('Ошибка', safe_calc(''))
        self.assertIn('Ошибка', safe_calc('1+' * 200 + '1'))


class ParseActionTest(unittest.TestCase):
    def test_valid_search(self):
        a = parse_action('{"action": "search", "input": "курс доллара", "reason": "нужны данные"}')
        self.assertEqual(a['action'], 'search')
        self.assertEqual(a['input'], 'курс доллара')

    def test_valid_finish_with_noise(self):
        a = parse_action('Вот мой ответ:\n{"action": "finish", "input": "# Отчёт\\nГотово"}')
        self.assertEqual(a['action'], 'finish')
        self.assertIn('Отчёт', a['input'])

    def test_invalid_action(self):
        self.assertIsNone(parse_action('{"action": "hack", "input": "x"}'))

    def test_not_json(self):
        self.assertIsNone(parse_action('просто текст без json'))
        self.assertIsNone(parse_action(''))
        self.assertIsNone(parse_action(None))

    def test_step_human(self):
        self.assertIn('Ищу', step_human({'action': 'search', 'input': 'q'}))
        self.assertIn('Вычисляю', step_human({'action': 'calc', 'input': '2+2'}))
        self.assertIn('отчёт', step_human({'action': 'finish', 'input': ''}))


if __name__ == '__main__':
    unittest.main()
