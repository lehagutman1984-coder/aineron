import json
from .base import BaseAgent, MODEL_SMART

FIXER_SYSTEM = (
    "Ты главный инженер. Сведи ReviewReport и TestReport в FixPlan для кодера. "
    "Верни СТРОГО JSON: {\"instructions\": \"конкретные правки текстом\", \"target_files\": [\"...\"], \"priority\": \"high|medium\"}."
)


class FixerAgent(BaseAgent):
    name = 'fixer'
    model = MODEL_SMART

    def run(self, review_report: dict, test_report: dict) -> dict:
        user = (
            f"ReviewReport:\n{json.dumps(review_report, ensure_ascii=False)}\n\n"
            f"TestReport:\n{json.dumps(test_report, ensure_ascii=False)}"
        )
        return self.run_json(FIXER_SYSTEM, user, model=MODEL_SMART, max_tokens=5000)
