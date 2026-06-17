from .base import BaseAgent, MODEL_SMART

DEVIATION_SYSTEM = (
    "Сравни план шага и реализованный код. Верни JSON: "
    '{"matched": [..], "deviations": [{"planned": "..", "actual": "..", "severity": "low|medium|high"}]}'
)


class DeviationReviewerAgent(BaseAgent):
    name = 'deviation'
    model = MODEL_SMART

    def review(self, planned: str, changed_files: dict) -> dict:
        body = '\n'.join(f'### {p}\n```\n{c[:4000]}\n```' for p, c in changed_files.items())
        user = f"ПЛАН ШАГА:\n{planned}\n\nРЕАЛИЗОВАНО:\n{body}"
        return self.run_json(DEVIATION_SYSTEM, user, model=self.resolve_model(), max_tokens=2000)
