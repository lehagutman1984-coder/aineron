from .base import BaseAgent, MODEL_FAST

INTERVIEWER_SYSTEM = (
    "Ты интервьюер для генератора веб-приложений. По краткому описанию проекта "
    "задай 3-5 уточняющих вопросов, которые помогут определить функционал, дизайн и стек. "
    "Верни СТРОГО JSON-массив объектов: "
    '[{"id": "q1", "question": "...", "type": "text|choice", "options": ["..."]}]. '
    "Без пояснений вне JSON."
)


class InterviewerAgent(BaseAgent):
    name = 'interviewer'
    model = MODEL_FAST

    def run(self) -> list:
        self.log('Формирую вопросы...')
        user = (
            f"Название: {self.project.name}\n"
            f"Описание: {self.project.description}\n"
            f"Стек: {self.project.target_stack}"
        )
        data = self.run_json(INTERVIEWER_SYSTEM, user, model=MODEL_FAST, max_tokens=2000)
        questions = data if isinstance(data, list) else data.get('questions', [])
        self.project.interview_data['questions'] = questions
        self.project.save(update_fields=['interview_data'])
        self.log(f'Готово: {len(questions)} вопросов')
        return questions
