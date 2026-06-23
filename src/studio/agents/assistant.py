from .base import BaseAgent, MODEL_FAST

ASSISTANT_SYSTEM = (
    "Ты ассистент студии генерации приложений. Пользователь на паузе пайплайна. "
    "Кратко отвечай на вопросы по проекту и предлагай, как продолжить (hint/skip). "
    "Контекст проекта дан ниже. Отвечай по-русски, по делу."
)


class AssistantAgent(BaseAgent):
    name = 'assistant'
    model = MODEL_FAST

    def answer(self, message: str, history: list) -> str:
        state = self.project.pipeline
        ctx = (
            f"PROJECT.md:\n{self.project.project_md_content[:3000]}\n\n"
            f"Текущий шаг: {state.step_index}\n"
            f"Причина паузы: {state.pause_reason}\n"
            f"Последняя ошибка: {(state.last_error or '')[:1000]}\n"
        )
        hist = '\n'.join(f"{h['role']}: {h['text']}" for h in history[-6:])
        user = f"{ctx}\nДиалог:\n{hist}\n\nВопрос: {message}"
        return self.run_prompt(ASSISTANT_SYSTEM, user, model=self.resolve_model(), max_tokens=32000, temperature=0.5)
