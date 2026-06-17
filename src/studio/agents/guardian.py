from .base import BaseAgent, pick_prompt

SYSTEM_EN = (
    "You are a senior code reviewer and QA engineer. Review the implemented code for a pipeline step.\n\n"
    "Check:\n"
    "1. Does it actually implement what the step planned?\n"
    "2. Missing imports, obvious syntax errors, undefined variables?\n"
    "3. Correct tech stack setup (Vite config with host:true port:3000, Next.js dev script 0.0.0.0:3000)?\n"
    "4. Production-ready: no TODO stubs, has error handling, no broken references?\n\n"
    "If build logs are provided: check for compilation errors.\n\n"
    "Be pragmatic: only flag REAL problems that would break the app. Style issues = pass.\n"
    "If this is a fix attempt, verify that previously flagged issues are now resolved.\n\n"
    "Return STRICTLY JSON:\n"
    '{"verdict": "pass" or "fix", '
    '"issues": ["list of real problems found, empty if pass"], '
    '"instructions": "specific actionable fix instructions in Russian (empty string if verdict=pass)", '
    '"target_files": ["path/to/file.ext (empty array if verdict=pass)"]}'
)

SYSTEM_RU = (
    "Ты старший ревьюер и QA-инженер. Проверь реализацию шага пайплайна.\n\n"
    "Проверь:\n"
    "1. Шаг реализован согласно плану?\n"
    "2. Нет пропущенных импортов, синтаксических ошибок, неопределённых переменных?\n"
    "3. Правильный стек (vite.config.ts host:true port:3000, Next.js dev 0.0.0.0:3000)?\n"
    "4. Production-ready: нет TODO, есть обработка ошибок?\n\n"
    "Если есть логи сборки: проверь на ошибки компиляции.\n\n"
    "Будь прагматичен: только реальные проблемы. Стиль = pass.\n\n"
    "Верни СТРОГО JSON:\n"
    '{"verdict": "pass" или "fix", '
    '"issues": ["список реальных проблем, пусто если pass"], '
    '"instructions": "конкретные инструкции по исправлению на русском (пустая строка если pass)", '
    '"target_files": ["путь/к/файлу (пустой массив если pass)"]}'
)


class GuardianAgent(BaseAgent):
    name = 'guardian'

    def run(self, step_text: str, files: dict, build_logs: str = '', attempt: int = 0) -> dict:
        system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
        files_content = '\n'.join(
            f'### {path}\n```\n{content[:3000]}\n```'
            for path, content in list(files.items())[:10]
        )
        build_section = (
            f'\n\nBuild logs:\n```\n{build_logs[-2000:]}\n```'
            if build_logs else ''
        )
        attempt_note = (
            f'\n\n(This is fix attempt #{attempt}. Verify previous issues are resolved.)'
            if attempt > 0 else ''
        )
        user = (
            f'Planned step:\n{step_text}\n\n'
            f'Implemented files:{attempt_note}\n{files_content}'
            f'{build_section}'
        )
        return self.run_json(system, user, model=self.resolve_model(), max_tokens=4096)
