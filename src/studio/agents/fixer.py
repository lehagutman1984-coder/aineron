import json
from .base import BaseAgent, pick_prompt

SYSTEM_RU = (
    "Ты ведущий инженер. Сведи ReviewReport и TestReport в чёткий FixPlan. "
    "Сначала — ошибки сборки, затем error-уровня ревью, затем warning. "
    "Инструкции конкретные: что именно и в каком файле поправить. Минимизируй target_files. "
    "Верни СТРОГО JSON: {\"instructions\":\"...\",\"target_files\":[\"...\"],\"priority\":\"high|medium\"}. "
    "instructions — на русском."
)

SYSTEM_EN = (
    "You are a lead engineer. Merge the ReviewReport and TestReport into a precise FixPlan for the coder. "
    "Prioritize: build errors first, then error-severity review issues, then warnings. "
    "Instructions must be concrete and actionable: exactly what to change and in which file. "
    "Keep target_files minimal (only genuinely affected files). "
    "Return STRICTLY JSON: {\"instructions\":\"...\",\"target_files\":[\"...\"],\"priority\":\"high|medium\"}. "
    "The \"instructions\" MUST be in Russian."
)


class FixerAgent(BaseAgent):
    name = 'fixer'

    def run(self, review_report: dict, test_report: dict) -> dict:
        system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
        user = (
            f"ReviewReport:\n{json.dumps(review_report, ensure_ascii=False)}\n\n"
            f"TestReport:\n{json.dumps(test_report, ensure_ascii=False)}"
        )
        return self.run_json(system, user, model=self.resolve_model(), max_tokens=5000)
