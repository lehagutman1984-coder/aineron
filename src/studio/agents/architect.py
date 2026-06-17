import json
from .base import BaseAgent, pick_prompt

SYSTEM_EN = (
    "You are a lead software architect. Given a project description, generate TWO documents:\n"
    "1. PROJECT.md — project specification: goals, tech stack, components, file structure, key dependencies.\n"
    "2. COMMITS.md — step-by-step implementation plan. Each step = one atomic coding session.\n\n"
    "COMMITS.md format:\n"
    "## Step 1: Project setup\n"
    "Description of what to implement...\n\n"
    "## Step 2: [COMPLEX] Core feature\n"
    "...\n\n"
    "Rules:\n"
    "- 5-15 steps total, each independently implementable\n"
    "- First step must set up project structure and package.json with ALL dependencies\n"
    "- Last step adds error handling and polish\n"
    "- Mark architecturally complex steps with [COMPLEX] in the title\n"
    "- For Vite/React/Vue: first step must include vite.config.ts with server:{host:true,port:3000,hmr:false}\n"
    "- For Next.js: package.json scripts.dev must be 'next dev -p 3000 -H 0.0.0.0'\n\n"
    "Return STRICTLY JSON (no markdown fences):\n"
    '{"project_md": "...full PROJECT.md content...", '
    '"commits_md": "...full COMMITS.md content...", '
    '"planned_steps": <integer count of steps>}'
)

SYSTEM_RU = (
    "Ты ведущий архитектор. На основе описания проекта сгенерируй два документа:\n"
    "1. PROJECT.md — спецификация: цели, стек, компоненты, структура файлов, зависимости.\n"
    "2. COMMITS.md — пошаговый план реализации. Каждый шаг = одна атомарная сессия кодинга.\n\n"
    "Формат COMMITS.md:\n"
    "## Шаг 1: Инициализация проекта\n"
    "Описание...\n\n"
    "## Шаг 2: [COMPLEX] Основная функция\n"
    "...\n\n"
    "Правила:\n"
    "- 5-15 шагов, каждый атомарен\n"
    "- Первый шаг: структура и package.json со ВСЕМИ зависимостями\n"
    "- Последний шаг: обработка ошибок и полировка\n"
    "- Архитектурно сложные шаги помечай [COMPLEX]\n"
    "- Для Vite/React/Vue: vite.config.ts с server:{host:true,port:3000,hmr:false}\n"
    "- Для Next.js: scripts.dev = 'next dev -p 3000 -H 0.0.0.0'\n\n"
    "Верни СТРОГО JSON (без markdown):\n"
    '{"project_md": "...полное PROJECT.md...", '
    '"commits_md": "...полное COMMITS.md...", '
    '"planned_steps": <число шагов>}'
)


class ArchitectAgent(BaseAgent):
    name = 'architect'

    def run(self, description: str, stack: str, features: list, answers: list) -> dict:
        system = pick_prompt(SYSTEM_RU, SYSTEM_EN)
        answers_text = ''
        if answers:
            answers_text = '\n\nAdditional context from user interview:\n'
            for a in answers:
                q = a.get('question', '') if isinstance(a, dict) else ''
                ans = a.get('answer', '') if isinstance(a, dict) else str(a)
                answers_text += f'Q: {q}\nA: {ans}\n'
        crawled_text = ''
        crawled = (self.project.interview_data or {}).get('crawled', {})
        if crawled:
            crawled_text = (
                f"\n\nCrawled site content:\n"
                f"Title: {crawled.get('title', '')}\n"
                f"{crawled.get('text', '')[:4000]}"
            )
        features_str = ', '.join(features) if features else 'standard set'
        user = (
            f"Project description: {description}\n"
            f"Stack: {stack}\n"
            f"Features: {features_str}"
            f"{answers_text}"
            f"{crawled_text}"
        )
        return self.run_json(system, user, model=self.resolve_model(), max_tokens=8192)
