import re
from .base import BaseAgent, pick_prompt

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

    # Extract INSTRUCTIONS
    instructions = ''
    instr_m = re.search(r'INSTRUCTIONS\s*:\s*\n(.*?)(?=FILES\s*:|$)',
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

    return {
        'verdict': verdict,
        'issues': issues,
        'instructions': instructions,
        'target_files': target_files,
    }


class GuardianAgent(BaseAgent):
    name = 'guardian'

    def run(self, step_text: str, files: dict, build_logs: str = '', attempt: int = 0) -> dict:
        system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
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
            f'Planned step:\n{step_text}\n\n'
            f'Implemented files:{attempt_note}\n{files_content}'
            f'{build_section}'
        )
        raw = self.run_prompt(system, user, model=self.resolve_model(), max_tokens=2048)
        return _parse_guardian_response(raw)
