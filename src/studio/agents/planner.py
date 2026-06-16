import re

from .base import BaseAgent, pick_prompt

SYSTEM_RU = (
    "Ты технический планировщик. На основе PROJECT.md составь COMMITS.md — пошаговый план реализации. "
    "Каждый шаг атомарный: заголовок, краткая цель, точный список файлов. "
    "Порядок учитывает зависимости. Помечай заголовок тегом [COMPLEX] если шаг включает auth, оплату, "
    "интеграции, realtime, миграции БД или затрагивает 5+ файлов. Не превышай 15 шагов. "
    "В конце: <STEPS_COUNT>N</STEPS_COUNT>. Markdown на русском, без преамбулы."
)

SYSTEM_EN = (
    "You are a technical planner. From PROJECT.md, produce COMMITS.md — a step-by-step implementation plan. "
    "Each step is atomic: a heading, a one-line goal, and the exact list of files created/modified. "
    "Order by dependency (scaffold first, then components, then integrations). "
    "Tag a heading [COMPLEX] if it involves auth, payments, third-party integrations, realtime, "
    "DB migrations, or touches 5+ files. Do not exceed 15 steps. "
    "End with <STEPS_COUNT>N</STEPS_COUNT>. Output Markdown in Russian, no preamble."
)


class PlannerAgent(BaseAgent):
    name = 'planner'

    def run(self) -> tuple:
        self.log('Составляю план реализации...')
        system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
        user = f"PROJECT.md:\n\n{self.project.project_md_content}"
        features = (self.project.interview_data or {}).get('features', [])
        if features:
            features_text = '\n'.join(f'- {f}' for f in features)
            user += (
                f'\n\nMUST-HAVE компоненты (выбраны пользователем, обязательны):\n{features_text}\n'
                f'Каждая функция должна быть покрыта хотя бы одним шагом COMMITS.md.'
            )
        md_raw = self.run_prompt(system, user, model=self.resolve_model(), max_tokens=8192)
        m = re.search(r'<STEPS_COUNT>(\d+)</STEPS_COUNT>', md_raw)
        marker = int(m.group(1)) if m else 0
        md = re.sub(r'<STEPS_COUNT>\d+</STEPS_COUNT>', '', md_raw).strip()
        from ..tasks import _split_steps
        steps = len(_split_steps(md)) or marker or 5
        if steps > 15:
            self.log(f'Предупреждение: план содержит {steps} шагов (рекомендуется не более 15)', level='warning')
        self.project.commits_md_content = md
        self.project.save(update_fields=['commits_md_content'])
        self.log(f'COMMITS.md готов: {steps} шагов')
        return md, steps
