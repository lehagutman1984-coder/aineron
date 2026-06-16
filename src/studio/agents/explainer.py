from .base import BaseAgent, MODEL_FAST

EXPLAINER_SYSTEM = (
    "Ты объясняешь код простыми словами по-русски. Кратко: что делает фрагмент, "
    "ключевые моменты, потенциальные проблемы. Без воды."
)


class ExplainerAgent(BaseAgent):
    name = 'explainer'
    model = MODEL_FAST

    def explain(self, code: str, path: str = '') -> str:
        user = f"Файл: {path}\n\nКод:\n```\n{code[:4000]}\n```"
        return self.run_prompt(EXPLAINER_SYSTEM, user, model=MODEL_FAST, max_tokens=1200, temperature=0.3)
