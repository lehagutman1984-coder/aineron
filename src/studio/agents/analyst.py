from .base import BaseAgent, pick_prompt

SYSTEM_RU = (
    "Ты системный аналитик. На основе описания проекта и ответов интервью составь технический документ "
    "PROJECT.md: цель, целевая аудитория, функциональные требования (нумерованный список), карта страниц, "
    "модель данных, стек и обоснование, нефункциональные требования (производительность, адаптив, доступность), "
    "ограничения и допущения. Документ должен быть конкретным и реализуемым. "
    "Markdown на русском, без преамбулы."
)

SYSTEM_EN = (
    "You are a systems analyst. Using the project description and interview answers, produce a technical "
    "PROJECT.md document containing: goal, target audience, functional requirements (numbered), page map, "
    "data model, chosen stack with justification, non-functional requirements (performance, responsiveness, "
    "accessibility), constraints and assumptions. Be concrete and buildable — avoid vague aspirations. "
    "Output Markdown in Russian, no preamble."
)


class AnalystAgent(BaseAgent):
    name = 'analyst'

    def run(self) -> str:
        self.log('Анализирую требования...')
        system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
        interview = self.project.interview_data
        user = (
            f"Project name: {self.project.name}\n"
            f"Description: {self.project.description}\n"
            f"Stack: {self.project.target_stack}\n"
            f"Interview data: {interview}"
        )
        features = (self.project.interview_data or {}).get('features', [])
        if features:
            features_text = '\n'.join(f'- {f}' for f in features)
            user += (
                f'\n\nОБЯЗАТЕЛЬНЫЕ ФУНКЦИИ (выбраны пользователем):\n{features_text}\n'
                f'Включи все эти функции в функциональные требования PROJECT.md.'
            )
        md = self.run_prompt(system, user, model=self.resolve_model(), max_tokens=8192)
        self.project.project_md_content = md
        self.project.save(update_fields=['project_md_content'])
        self.log('PROJECT.md готов')
        return md
