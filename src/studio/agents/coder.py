from .base import BaseAgent, MODEL_FAST

CODER_SYSTEM = (
    "Ты senior-разработчик. Реализуй ОДИН шаг из COMMITS.md. "
    "Верни СТРОГО JSON: {\"files\": {\"относительный/путь\": \"полное содержимое файла\"}}. "
    "Пиши полные файлы целиком, не диффы. Учитывай существующие файлы (даны в контексте)."
)


class CoderAgent(BaseAgent):
    name = 'coder'
    model = MODEL_FAST

    def run(self, step_index: int, step_text: str, existing_files: dict) -> dict:
        ctx = '\n'.join(f'- {p}' for p in existing_files.keys()) or '(пусто)'
        user = (
            f"PROJECT.md:\n{self.project.project_md_content}\n\n"
            f"Текущий шаг #{step_index}:\n{step_text}\n\n"
            f"Существующие файлы:\n{ctx}\n\n"
            f"Содержимое ключевых файлов:\n"
            + '\n'.join(f'### {p}\n{c[:2000]}' for p, c in list(existing_files.items())[:10])
        )
        data = self.run_json(CODER_SYSTEM, user, model=MODEL_FAST, max_tokens=8192)
        return data.get('files', {})
