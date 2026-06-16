from .base import BaseAgent, MODEL_FAST

TESTER_SYSTEM = (
    "Ты QA-инженер. Проанализируй логи sandbox. Определи ошибки компиляции/рантайма. "
    "Верни СТРОГО JSON TestReport: "
    '{"passed": bool, "errors": [{"type": "build|runtime", "message": "...", "file": "..."}], "build_ok": bool, "summary": "..."}.'
)


class TesterAgent(BaseAgent):
    name = 'tester'
    model = MODEL_FAST

    def run(self, build_logs: str, exit_code=None) -> dict:
        user = f"exit_code={exit_code}\nЛоги сборки:\n{build_logs[-6000:]}"
        report = self.run_json(TESTER_SYSTEM, user, model=MODEL_FAST, max_tokens=4000)
        if exit_code is not None and exit_code != 0:
            report['build_ok'] = False
            report['passed'] = False
        report.setdefault('passed', report.get('build_ok', False) and not report.get('errors'))
        return report
