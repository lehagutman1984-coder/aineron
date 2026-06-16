from .base import BaseAgent, pick_prompt

SYSTEM_RU = (
    "Ты QA-инженер. Проанализируй логи сборки из sandbox и exit_code. "
    "Определи ошибки компиляции и рантайма. Если exit_code != 0 — build_ok=false. "
    "Верни СТРОГО JSON: {\"passed\":bool,\"errors\":[{\"type\":\"build|runtime\",\"message\":\"...\",\"file\":\"...\"}],\"build_ok\":bool,\"summary\":\"...\"}. "
    "summary — на русском."
)

SYSTEM_EN = (
    "You are a QA engineer. Analyze the sandbox build/typecheck logs and exit_code. "
    "Identify compilation (TS/build) and runtime errors. If exit_code != 0 then build_ok=false. "
    "Return STRICTLY JSON: {\"passed\":bool,\"errors\":[{\"type\":\"build|runtime\",\"message\":\"...\",\"file\":\"...\"}],\"build_ok\":bool,\"summary\":\"...\"}. "
    "The \"summary\" and \"message\" MUST be in Russian."
)


class TesterAgent(BaseAgent):
    name = 'tester'

    def run(self, build_logs: str, exit_code=None) -> dict:
        system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
        user = f"exit_code={exit_code}\nBuild logs:\n{build_logs[-6000:]}"
        report = self.run_json(system, user, model=self.resolve_model(), max_tokens=4000)
        if exit_code is not None and exit_code != 0:
            report['build_ok'] = False
            report['passed'] = False
        report.setdefault('passed', report.get('build_ok', False) and not report.get('errors'))
        return report
