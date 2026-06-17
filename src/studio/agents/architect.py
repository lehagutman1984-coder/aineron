import re
from .base import BaseAgent, pick_prompt

SYSTEM_PROJECT_EN = (
    "You are a lead software architect. Write a PROJECT.md specification document.\n"
    "Include: project goals, tech stack, components, file structure, key dependencies.\n"
    "Output ONLY the markdown content — no extra commentary, no JSON, no code fences."
)

SYSTEM_PROJECT_RU = (
    "Ты ведущий архитектор ПО. Напиши документ PROJECT.md — спецификацию проекта.\n"
    "Включи: цели проекта, технологический стек, компоненты, структуру файлов, ключевые зависимости.\n"
    "Выводи ТОЛЬКО markdown-контент — без лишних комментариев, без JSON, без code-блоков."
)

SYSTEM_COMMITS_EN = (
    "You are a lead software architect. Write a COMMITS.md implementation plan.\n\n"
    "Format each step as:\n"
    "## Step N: Title\n"
    "What to implement in this step...\n\n"
    "Rules:\n"
    "- 5-15 steps total, each independently implementable\n"
    "- Step 1: project setup + package.json with ALL dependencies\n"
    "- Last step: error handling and polish\n"
    "- Mark complex steps with [COMPLEX] in the title\n"
    "- For Vite/React/Vue: step 1 must include vite.config.ts with server:{host:true,port:3000,hmr:false}\n"
    "- For Next.js: package.json scripts.dev must be 'next dev -p 3000 -H 0.0.0.0'\n\n"
    "Output ONLY the markdown steps — no extra commentary, no JSON, no code fences."
)

SYSTEM_COMMITS_RU = (
    "Ты ведущий архитектор ПО. Напиши COMMITS.md — пошаговый план реализации.\n\n"
    "Формат каждого шага:\n"
    "## Шаг N: Название\n"
    "Что реализовать на этом шаге...\n\n"
    "Правила:\n"
    "- 5-15 шагов, каждый атомарен\n"
    "- Шаг 1: инициализация проекта + package.json со ВСЕМИ зависимостями\n"
    "- Последний шаг: обработка ошибок и полировка\n"
    "- Архитектурно сложные шаги помечай [COMPLEX]\n"
    "- Для Vite/React/Vue: vite.config.ts с server:{host:true,port:3000,hmr:false}\n"
    "- Для Next.js: scripts.dev = 'next dev -p 3000 -H 0.0.0.0'\n\n"
    "Выводи ТОЛЬКО markdown-шаги — без лишних комментариев, без JSON, без code-блоков."
)


class ArchitectAgent(BaseAgent):
    name = 'architect'

    def run(self, description: str, stack: str, features: list, answers: list) -> dict:
        model = self.resolve_model()
        context = self._build_context(description, stack, features, answers)

        system_project = pick_prompt(SYSTEM_PROJECT_RU, SYSTEM_PROJECT_EN)
        project_md = self.run_prompt(
            system_project,
            context,
            model=model,
            max_tokens=4096,
            temperature=0.3,
        )

        system_commits = pick_prompt(SYSTEM_COMMITS_RU, SYSTEM_COMMITS_EN)
        commits_md = self.run_prompt(
            system_commits,
            context + f"\n\nPROJECT.md already written:\n{project_md[:2000]}",
            model=model,
            max_tokens=4096,
            temperature=0.3,
        )

        planned_steps = len(re.findall(r'^##\s+(?:Step|Шаг)\s+\d+', commits_md, re.MULTILINE))
        if not planned_steps:
            planned_steps = len(re.findall(r'^##\s+', commits_md, re.MULTILINE))
        if not planned_steps:
            planned_steps = 5

        return {
            'project_md': project_md.strip(),
            'commits_md': commits_md.strip(),
            'planned_steps': planned_steps,
        }

    def _build_context(self, description: str, stack: str, features: list, answers: list) -> str:
        parts = [
            f"Project description: {description}",
            f"Stack: {stack}",
            f"Features: {', '.join(features) if features else 'standard set'}",
        ]
        if answers:
            parts.append("\nAdditional context from user interview:")
            for a in answers:
                q = a.get('question', '') if isinstance(a, dict) else ''
                ans = a.get('answer', '') if isinstance(a, dict) else str(a)
                parts.append(f"Q: {q}\nA: {ans}")
        crawled = (self.project.interview_data or {}).get('crawled', {})
        if crawled:
            parts.append(
                f"\nCrawled site:\nTitle: {crawled.get('title', '')}\n"
                f"{crawled.get('text', '')[:3000]}"
            )
        return '\n'.join(parts)
