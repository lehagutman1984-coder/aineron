#!/usr/bin/env python3
"""
CI-скрипт: проверяет отсутствие эмодзи в шаблонах, JS и Python-файлах.
Завершается с кодом 1 если найдены эмодзи.

Использование:
    python scripts/check_no_emoji.py
    python scripts/check_no_emoji.py --fix    # показывает детали
"""
import re
import sys
import os

# Диапазоны Unicode для эмодзи (без базовых символов типа →, ·, ₽)
EMOJI_PATTERN = re.compile(
    r'[\U0001F300-\U0001F9FF]'  # Misc Symbols and Pictographs, Emoticons, etc.
    r'|[\U0001FA00-\U0001FAFF]'  # Symbols and Pictographs Extended-A
    r'|[☀-➿]'          # Misc Symbols, Dingbats (★☀✅❌⚠️⭐ etc.)
    r'|[⌀-⏿]'          # Misc Technical (⏱️⏩ etc.)
    r'|[⬀-⯿]'          # Misc Symbols and Arrows
    r'|[〰〽㊗㊙]'  # CJK symbols
)

SCAN_DIRS = [
    'src/templates',
    'src/static/neuro/js',
]
SCAN_PYTHON_DIRS = [
    'src/aitext',
    'src/users',
    'src/blog',
    'src/landing',
    'src/config',
]
EXCLUDE_DIRS = {'__pycache__', 'migrations', '.git', 'node_modules', 'venv', '.venv'}
EXCLUDE_FILES = {'check_no_emoji.py'}
PYTHON_EXCLUDE_PATTERNS = ['test_', '_test.py', 'fixtures']


def should_skip_file(path):
    basename = os.path.basename(path)
    if basename in EXCLUDE_FILES:
        return True
    # Skip test files for Python
    for pat in PYTHON_EXCLUDE_PATTERNS:
        if pat in path:
            return True
    return False


def scan_file(path):
    findings = []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for lineno, line in enumerate(f, 1):
                for match in EMOJI_PATTERN.finditer(line):
                    findings.append((lineno, match.group(), line.rstrip()))
    except Exception as e:
        pass
    return findings


def scan_dir(directory, extensions):
    results = {}
    if not os.path.isdir(directory):
        return results
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in files:
            if any(fname.endswith(ext) for ext in extensions):
                fpath = os.path.join(root, fname)
                if should_skip_file(fpath):
                    continue
                findings = scan_file(fpath)
                if findings:
                    results[fpath] = findings
    return results


def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(base)

    all_results = {}

    for d in SCAN_DIRS:
        all_results.update(scan_dir(d, ['.html', '.js', '.css']))

    for d in SCAN_PYTHON_DIRS:
        all_results.update(scan_dir(d, ['.py']))

    if not all_results:
        print('[OK] No emoji found in templates/JS/Python files.')
        return 0

    print(f'[FAIL] Found emoji in {len(all_results)} file(s):\n')
    for path, findings in sorted(all_results.items()):
        for lineno, char, line in findings:
            print(f'  {path}:{lineno}  U+{ord(char):04X} ({char!r})  {line[:120]}')
    print(f'\nTotal: {sum(len(v) for v in all_results.values())} occurrence(s) in {len(all_results)} file(s).')
    print('Fix: replace emoji with text or SVG icons per design policy.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
