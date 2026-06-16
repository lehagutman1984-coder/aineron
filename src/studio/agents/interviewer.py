from .base import BaseAgent, pick_prompt

SYSTEM_RU = (
    "Ты интервьюер сервиса генерации веб-приложений. По краткому описанию проекта задай 3-5 умных "
    "уточняющих вопросов, которые реально влияют на функционал, дизайн и стек. "
    "Не задавай очевидных или избыточных вопросов. Для вопросов с выбором давай 2-4 варианта. "
    "Верни СТРОГО JSON-массив: [{\"id\":\"q1\",\"question\":\"...\",\"type\":\"text|choice\",\"options\":[\"...\"]}]. "
    "Вопросы — на русском. Никакого текста вне JSON."
)

SYSTEM_EN = (
    "You are an interviewer for a web-app generation service. Given a short project description, "
    "ask 3-5 smart clarifying questions that materially affect scope, design, and stack. "
    "Do not ask obvious or redundant questions. Respect the chosen stack (Next.js/React/Vue/HTML). "
    "For choice questions provide 2-4 options. "
    "Return STRICTLY a JSON array: [{\"id\":\"q1\",\"question\":\"...\",\"type\":\"text|choice\",\"options\":[\"...\"]}]. "
    "The \"question\" and \"options\" text MUST be written in Russian. Output nothing outside the JSON."
)


class InterviewerAgent(BaseAgent):
    name = 'interviewer'

    def run(self) -> list:
        self.log('Формирую вопросы...')
        system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
        user = (
            f"Project name: {self.project.name}\n"
            f"Description: {self.project.description}\n"
            f"Stack: {self.project.target_stack}"
        )
        data = self.run_json(system, user, model=self.resolve_model(), max_tokens=2000)
        questions = data if isinstance(data, list) else data.get('questions', [])
        self.project.interview_data['questions'] = questions
        self.project.save(update_fields=['interview_data'])
        self.log(f'Готово: {len(questions)} вопросов')
        return questions
