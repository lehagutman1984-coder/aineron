import re
from .base import BaseAgent, pick_prompt
from django.conf import settings as _global_settings

SYSTEM_PROJECT_EN = (
    "You are a lead software architect. Write a PROJECT.md specification document.\n"
    "Include: project goals, tech stack, components, file structure, key dependencies.\n"
    "IMPORTANT: Write all content in Russian.\n"
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
    "## Шаг N: Название шага\n"
    "Описание что реализовать на этом шаге...\n\n"
    "Rules:\n"
    "- 5-15 steps total, each independently implementable\n"
    "- Step 1: project setup + package.json with ALL dependencies\n"
    "- Last step: error handling and polish\n"
    "- Mark complex steps with [COMPLEX] in the title\n"
    "- For Vite/React/Vue: step 1 must include vite.config.ts with server:{host:true,port:3000,hmr:false}\n"
    "- For Next.js: package.json scripts.dev must be 'next dev -p 3000 -H 0.0.0.0'\n\n"
    "IMPORTANT: Write ALL step titles and descriptions in Russian.\n"
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


ARCHITECT_DESIGN_RU = (
    "Ты ведущий продуктовый дизайнер. Напиши DESIGN.md — дизайн-систему проекта.\n"
    "Ориентир: Linear, Vercel, Stripe — строгий минимализм, профессионально.\n"
    "Включи разделы: Дизайн-направление; Цветовая палитра (CSS-переменные, тёмная+светлая тема);\n"
    "Типографика (шрифт Inter, размеры, веса); Компоненты по умолчанию (кнопки, карточки,\n"
    "инпуты — с КОНКРЕТНЫМИ Tailwind-классами); Сетка и отступы; Иконки (только lucide-react,\n"
    "без эмодзи); Состояния (loading/empty/error).\n"
    "Давай КОНКРЕТНЫЕ значения (#hex, rounded-lg, h-10), не общие слова.\n"
    "Выводи ТОЛЬКО markdown. На русском. Без JSON, без code-fences вокруг всего документа."
)
ARCHITECT_DESIGN_EN = (
    "You are a lead product designer. Write DESIGN.md — the project's design system.\n"
    "Reference: Linear, Vercel, Stripe — strict minimalism, professional.\n"
    "Include sections: Design direction; Color palette (CSS variables, dark+light);\n"
    "Typography (Inter font, sizes, weights); Default components (buttons, cards, inputs —\n"
    "with CONCRETE Tailwind classes); Grid & spacing; Icons (lucide-react only, no emoji);\n"
    "States (loading/empty/error).\n"
    "Give CONCRETE values (#hex, rounded-lg, h-10), not vague words.\n"
    "Output ONLY markdown. Write content in Russian. No JSON, no outer code fences."
)

ARCHITECT_COMMITS_V3_RU = (
    "Ты ведущий архитектор. Составь пошаговый план COMMITS.md.\n\n"
    "ЖЁСТКИЕ ПРАВИЛА ДЕКОМПОЗИЦИИ:\n"
    "- Каждый файл <= 200 строк. Если выйдет больше — РАЗБЕЙ на несколько файлов.\n"
    "- <= 5 файлов на шаг. Файлы шага логически связаны (один экран/фича).\n"
    "- Один компонент = один файл. Логика (хуки/утилиты/типы) отдельно от UI.\n"
    "- Моки и данные — в lib/data.ts, не внутри компонента.\n"
    "- 6-14 шагов. Шаг 1: package.json + конфиги + точка входа + UI-примитивы (ui/).\n"
    "- Для Vite: vite.config.ts с server:{host:true,port:3000,hmr:false}.\n"
    "- Для Next.js: scripts.dev = 'next dev -p 3000 -H 0.0.0.0'.\n"
    "- Архитектурно сложные шаги помечай [COMPLEX] в заголовке.\n\n"
    "ФОРМАТ КАЖДОГО ШАГА СТРОГО:\n"
    "## Шаг N: Название\n"
    "Описание что реализовать.\n"
    "FILES:\n"
    "- путь/файл.tsx | <=120 | роль файла\n"
    "- путь/файл2.ts | <=60 | роль файла\n\n"
    "Выводи ТОЛЬКО markdown. Без JSON, без code-fences."
)
ARCHITECT_COMMITS_V3_EN = (
    "You are a lead architect. Write a COMMITS.md implementation plan.\n\n"
    "STRICT DECOMPOSITION RULES:\n"
    "- Each file <= 200 lines. If it would be larger — SPLIT into several files.\n"
    "- <= 5 files per step. Files in a step are logically related (one screen/feature).\n"
    "- One component = one file. Logic (hooks/utils/types) separate from UI.\n"
    "- Mocks and data in lib/data.ts, not inside components.\n"
    "- 6-14 steps. Step 1: package.json + configs + entry point + UI primitives (ui/).\n"
    "- For Vite: vite.config.ts with server:{host:true,port:3000,hmr:false}.\n"
    "- For Next.js: scripts.dev = 'next dev -p 3000 -H 0.0.0.0'.\n"
    "- Mark architecturally complex steps with [COMPLEX] in the title.\n\n"
    "EACH STEP FORMAT STRICTLY:\n"
    "## Шаг N: Title\n"
    "Description of what to implement.\n"
    "FILES:\n"
    "- path/file.tsx | <=120 | file role\n"
    "- path/file2.ts | <=60 | file role\n\n"
    "Write step titles/descriptions in Russian. Output ONLY markdown. No JSON, no code fences."
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

        design_md = ''
        if _global_settings.STUDIO_V3:
            system_design = pick_prompt(ARCHITECT_DESIGN_RU, ARCHITECT_DESIGN_EN)
            design_md = self.run_prompt(
                system_design,
                context + f"\n\nPROJECT.md:\n{project_md[:2000]}",
                model=model, max_tokens=3000, temperature=0.4,
            )

        if _global_settings.STUDIO_V3:
            system_commits = pick_prompt(ARCHITECT_COMMITS_V3_RU, ARCHITECT_COMMITS_V3_EN)
        else:
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

        result = {
            'project_md': project_md.strip(),
            'commits_md': commits_md.strip(),
            'planned_steps': planned_steps,
        }
        if _global_settings.STUDIO_V3:
            result['design_md'] = design_md.strip()
            result['plan'] = self._parse_plan(commits_md)
        return result

    def _parse_plan(self, commits_md: str) -> list:
        """
        Парсит COMMITS.md в структурированный план:
        [{step, title, description, files:[{path, max_lines, role}]}, ...]
        Устойчив к отсутствию секции FILES: (тогда files=[]).
        """
        plan = []
        sections = re.split(r'\n(?=##\s+(?:Step|Шаг)\s+\d+)', commits_md or '')
        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue
            title_m = re.match(r'##\s+(?:Step|Шаг)\s+(\d+)\s*:?\s*(.*)', sec)
            if not title_m:
                continue
            step_num = int(title_m.group(1))
            title = title_m.group(2).strip()
            files = []
            fm = re.search(r'FILES\s*:\s*\n(.*?)(?=\n##\s|\Z)', sec, re.DOTALL | re.IGNORECASE)
            if fm:
                for line in fm.group(1).splitlines():
                    line = re.sub(r'^[\s\-\*]+', '', line).strip()
                    if not line:
                        continue
                    parts = [p.strip() for p in line.split('|')]
                    path = parts[0].lstrip('/')
                    max_lines = 200
                    role = ''
                    if len(parts) >= 2:
                        ml = re.search(r'(\d+)', parts[1])
                        if ml:
                            max_lines = int(ml.group(1))
                    if len(parts) >= 3:
                        role = parts[2]
                    if path:
                        files.append({'path': path, 'max_lines': max_lines, 'role': role})
            desc_m = re.search(r'##[^\n]*\n(.*?)(?=\nFILES\s*:|\Z)', sec, re.DOTALL | re.IGNORECASE)
            description = desc_m.group(1).strip() if desc_m else ''
            plan.append({
                'step': step_num, 'title': title,
                'description': description, 'files': files,
            })
        return plan

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
