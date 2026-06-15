from .base import BaseAgent, MODEL_SMART

ANALYST_SYSTEM = (
    "Ты системный аналитик. На основе описания проекта и ответов интервью составь "
    "технический документ PROJECT.md на русском: цель, функциональные требования, "
    "структура страниц, модель данных, стек, ограничения. Markdown, без преамбулы."
)


class AnalystAgent(BaseAgent):
    name = 'analyst'
    model = MODEL_SMART

    def run(self) -> str:
        self.log('Анализирую требования...')
        interview = self.project.interview_data
        user = (
            f"Название: {self.project.name}\n"
            f"Описание: {self.project.description}\n"
            f"Стек: {self.project.target_stack}\n"
            f"Интервью: {interview}"
        )
        md = self.run_prompt(ANALYST_SYSTEM, user, model=MODEL_SMART, max_tokens=8192)
        self.project.project_md_content = md
        self.project.save(update_fields=['project_md_content'])
        self.log('PROJECT.md готов')
        return md
