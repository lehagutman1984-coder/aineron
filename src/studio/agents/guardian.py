import re
from django.conf import settings
from .base import BaseAgent, pick_prompt

SYSTEM_TMA = (
    "Ты старший ревьюер Telegram Mini App. Проверь реализацию шага TMA-пайплайна.\n\n"
    "Специфичные TMA-проверки:\n"
    "1. WebApp.ready() вызывается в useEffect при монтировании (обязательно!)\n"
    "2. Тема: WebApp.colorScheme используется для dark/light переключения\n"
    "3. initData: если есть серверная валидация — проверяется через HMAC-SHA256 (WebAppData)\n"
    "4. Платежи: используется WebApp.openInvoice(), а не сторонние платёжные виджеты\n"
    "5. Навигация: нет window.location.href вместо WebApp.close()/onEvent\n"
    "6. Нет import 'react-router-dom' — TMA одноэкранные или используют state-машину\n\n"
    "Стандартные проверки:\n"
    "- Нет пропущенных импортов / зависимостей в package.json?\n"
    "- Vite: host:true port:3000 в vite.config.ts\n"
    "- Нет TODO-заглушек\n\n"
    "Только реальные проблемы — стиль = PASS.\n\n"
    "Ответь строго в формате:\n"
    "VERDICT: pass\n"
    "или\n"
    "VERDICT: fix\n"
    "ISSUES:\n"
    "- проблема\n"
    "INSTRUCTIONS:\n"
    "Конкретные инструкции исправления.\n"
    "FILES:\n"
    "- путь/к/файлу.ts"
)

SYSTEM_EN = (
    "You are a senior code reviewer. Review the implemented code for a pipeline step.\n\n"
    "IMPORTANT: Structural integrity (brace balance, truncation) has already been checked "
    "programmatically BEFORE you. Do NOT flag 'file looks truncated' — that is handled by code. "
    "If you cannot see the end of a large file, assume it is complete.\n\n"
    "Check:\n"
    "1. Does it implement what the step planned?\n"
    "2. Missing imports, undefined variables, missing dependencies in package.json?\n"
    "3. Correct stack setup (Vite: host:true port:3000; Next.js: dev script 0.0.0.0:3000)?\n"
    "4. No TODO stubs, has error handling, no broken references?\n"
    "If build logs are provided: check for compilation errors.\n\n"
    "Be pragmatic: only flag REAL problems that would break the app. Style issues = PASS.\n"
    "If this is a fix attempt, verify previous issues are now resolved.\n\n"
    "Respond in EXACTLY this format (no extra text):\n"
    "VERDICT: pass\n"
    "or\n"
    "VERDICT: fix\n"
    "ISSUES:\n"
    "- problem 1\n"
    "- problem 2\n"
    "INSTRUCTIONS:\n"
    "Specific actionable fix instructions in Russian.\n"
    "FILES:\n"
    "- path/to/file.ts"
)

SYSTEM_RU = (
    "Ты старший ревьюер. Проверь реализацию шага пайплайна.\n\n"
    "ВАЖНО: Структурная целостность файлов (баланс скобок, обрезка кода) уже проверена "
    "программно ДО тебя. НЕ выноси вердикт fix с формулировкой «файл выглядит обрезанным» — "
    "это уже обработано. Если не видишь конец большого файла — считай что он полный.\n\n"
    "Проверь:\n"
    "1. Шаг реализован согласно плану?\n"
    "2. Нет пропущенных импортов, отсутствующих зависимостей в package.json?\n"
    "3. Правильный стек (vite.config.ts host:true port:3000; Next.js dev 0.0.0.0:3000)?\n"
    "4. Нет TODO, есть обработка ошибок?\n"
    "Если есть логи сборки: проверь ошибки компиляции.\n\n"
    "Только реальные проблемы ломающие приложение. Стиль = PASS.\n\n"
    "Ответь СТРОГО в этом формате (без лишнего текста):\n"
    "VERDICT: pass\n"
    "или\n"
    "VERDICT: fix\n"
    "ISSUES:\n"
    "- проблема 1\n"
    "INSTRUCTIONS:\n"
    "Конкретные инструкции по исправлению.\n"
    "FILES:\n"
    "- путь/к/файлу.ts"
)


SYSTEM_V3_RU = (
    "Ты старший ревьюер. Структурная целостность (скобки, обрезка, импорты, сборка)\n"
    "УЖЕ проверена кодом ДО тебя — НЕ комментируй обрезку и баланс скобок.\n\n"
    "Проверь ТОЛЬКО:\n"
    "1. Реализован ли замысел шага (фичи на месте)?\n"
    "2. Соответствие DESIGN.md: токены вместо хардкод-цветов (#fff), lucide-иконки,\n"
    "   состояния loading/empty/error, отсутствие эмодзи?\n"
    "3. Логика: кнопки с обработчиками, формы с сабмитом, нет мёртвых ссылок?\n"
    "Если есть build-логи с ошибкой — учти их.\n\n"
    "Только реальные проблемы. Стиль = PASS.\n\n"
    "Для ЛОКАЛЬНЫХ правок выдавай EDIT blocks (точечные диффы), НЕ перегенерацию:\n"
    "=== EDIT: <путь> ===\n"
    "<<<<<<< SEARCH\n<точный текущий кусок>\n=======\n<новый кусок>\n>>>>>>> REPLACE\n"
    "=== END EDIT ===\n"
    "SEARCH должен ТОЧНО совпадать с текущим кодом (включая отступы).\n\n"
    "Ответь СТРОГО:\n"
    "VERDICT: pass\nили\nVERDICT: fix\n"
    "ISSUES:\n- проблема\n"
    "INSTRUCTIONS:\nКонкретные инструкции.\n"
    "EDITS:\n<edit blocks или пусто>\n"
    "FILES:\n- путь (только если нужна ПОЛНАЯ перегенерация файла)"
)
SYSTEM_V3_EN = (
    "You are a senior reviewer. Structural integrity (braces, truncation, imports,\n"
    "build) is ALREADY checked by code BEFORE you — do NOT comment on truncation or braces.\n\n"
    "Check ONLY:\n"
    "1. Is the step's intent implemented (features present)?\n"
    "2. DESIGN.md compliance: design tokens instead of hardcoded colors, lucide icons,\n"
    "   loading/empty/error states, no emoji?\n"
    "3. Logic: buttons with handlers, forms with submit, no dead links?\n"
    "If build logs with errors are provided — account for them.\n\n"
    "Only real problems. Style = PASS.\n\n"
    "For LOCAL fixes emit EDIT blocks (search/replace diffs), NOT full regeneration:\n"
    "=== EDIT: <path> ===\n"
    "<<<<<<< SEARCH\n<exact current snippet>\n=======\n<new snippet>\n>>>>>>> REPLACE\n"
    "=== END EDIT ===\n"
    "SEARCH must EXACTLY match current code (including indentation).\n\n"
    "Respond STRICTLY:\n"
    "VERDICT: pass\nor\nVERDICT: fix\n"
    "ISSUES:\n- problem\n"
    "INSTRUCTIONS:\nConcrete fix instructions in Russian.\n"
    "EDITS:\n<edit blocks or empty>\n"
    "FILES:\n- path (only if FULL regeneration is needed)"
)


def _parse_guardian_response(text: str) -> dict:
    """Parse plain-text guardian response into a structured dict."""
    text = text.strip()

    # Extract VERDICT
    m = re.search(r'VERDICT\s*:\s*(pass|fix)', text, re.IGNORECASE)
    verdict = m.group(1).lower() if m else 'pass'

    # Extract ISSUES list
    issues = []
    issues_m = re.search(r'ISSUES\s*:\s*\n(.*?)(?=INSTRUCTIONS\s*:|FILES\s*:|$)',
                         text, re.DOTALL | re.IGNORECASE)
    if issues_m:
        for line in issues_m.group(1).splitlines():
            line = re.sub(r'^[\s\-\*]+', '', line).strip()
            if line:
                issues.append(line)

    # Extract INSTRUCTIONS (lookahead includes EDITS: to avoid swallowing EDIT blocks)
    instructions = ''
    instr_m = re.search(r'INSTRUCTIONS\s*:\s*\n(.*?)(?=EDITS\s*:|FILES\s*:|$)',
                        text, re.DOTALL | re.IGNORECASE)
    if instr_m:
        instructions = instr_m.group(1).strip()

    # Extract FILES
    target_files = []
    files_m = re.search(r'FILES\s*:\s*\n(.*?)$', text, re.DOTALL | re.IGNORECASE)
    if files_m:
        for line in files_m.group(1).splitlines():
            line = re.sub(r'^[\s\-\*]+', '', line).strip()
            if line:
                target_files.append(line)

    # Extract EDIT blocks (V3 only)
    edits = []
    try:
        if settings.STUDIO_V3:
            from .edits import parse_edits
            edits_m = re.search(r'EDITS\s*:\s*\n(.*?)(?=\nFILES\s*:|$)',
                                text, re.DOTALL | re.IGNORECASE)
            edits_text = edits_m.group(1) if edits_m else text
            edits = parse_edits(edits_text)
    except Exception:
        edits = []

    return {
        'verdict': verdict,
        'issues': issues,
        'instructions': instructions,
        'target_files': target_files,
        'edits': edits,
    }


class GuardianAgent(BaseAgent):
    name = 'guardian'

    @staticmethod
    def _build_symbol_map(all_files: dict) -> str:
        """Extract exported names/functions per file for cross-file reference check."""
        import re as _re
        lines = []
        for path, content in list(all_files.items())[:40]:
            if not path.endswith(('.js', '.jsx', '.ts', '.tsx', '.py')):
                continue
            exports = _re.findall(
                r'export\s+(?:default\s+)?(?:function|class|const|let|var|type|interface)\s+(\w+)',
                content,
            )
            defs = _re.findall(r'^def\s+(\w+)', content, _re.MULTILINE)
            names = exports + defs
            if names:
                lines.append(f'{path}: {", ".join(names[:15])}')
        return '\n'.join(lines)

    def run(self, step_text: str, files: dict, build_logs: str = '', attempt: int = 0) -> dict:
        is_tma = (
            getattr(settings, 'STUDIO_V4_TMA', False)
            and getattr(self.project, 'target_stack', '') == 'tma'
        )
        if is_tma:
            system = SYSTEM_TMA
            design_section = ''
        elif settings.STUDIO_V3:
            system = pick_prompt(SYSTEM_V3_RU, SYSTEM_V3_EN)
            design = (getattr(self.project, 'design_md_content', '') or '')[:2000]
            design_section = f'\n\nDESIGN.md (проверь соответствие):\n{design}' if design else ''
        else:
            system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
            design_section = ''
        # V4: full project symbol map for cross-file reference verification
        symbol_section = ''
        if getattr(settings, 'STUDIO_V4_GUARDIAN_CONTEXT', False):
            try:
                all_proj_files = {
                    f.path: f.content
                    for f in self.project.files.all()
                }
            except Exception:
                all_proj_files = {}
            if all_proj_files:
                sym = self._build_symbol_map(all_proj_files)
                if sym:
                    symbol_section = f'\n\nProject exports (cross-file check):\n{sym}'
        files_content = '\n'.join(
            f'### {path}\n```\n{content[:8000]}\n```'
            for path, content in list(files.items())[:10]
        )
        build_section = (
            f'\n\nBuild logs:\n```\n{build_logs[-2000:]}\n```'
            if build_logs else ''
        )
        attempt_note = (
            f'\n\n(Fix attempt #{attempt}. Verify previous issues are resolved.)'
            if attempt > 0 else ''
        )
        user = (
            f'Planned step:\n{step_text}{design_section}{symbol_section}\n\n'
            f'Implemented files:{attempt_note}\n{files_content}'
            f'{build_section}'
        )
        raw = self.run_prompt(system, user, model=self.resolve_model(), max_tokens=32000)
        return _parse_guardian_response(raw)
