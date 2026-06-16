# STUDIO_COMMITS.md

План пошаговой разработки aineron.ru Studio v2 по коммитам.
Базовый продуктовый документ: `STUDIO_V2_PLAN.md`.

Этот файл — рабочая инструкция для исполнителя (человека или LLM). Каждый коммит описан настолько подробно, чтобы его можно было реализовать без дополнительных уточнений: указаны точные файлы, что именно изменить и готовый код. Реализуй коммиты строго по порядку — поздние зависят от ранних.

## Правила работы

- Один коммит = одна логическая единица. Не смешивать коммиты.
- После каждого коммита: `git add -A && git commit` с осмысленным сообщением, затем `git push origin main`.
- Дизайн-система обязательна: только иконки Lucide React (`import { X } from 'lucide-react'`), без эмодзи. Стили только через CSS-переменные (`var(--bg)`, `var(--card-bg)`, `var(--border)`, `var(--text)`, `var(--text-secondary)`, `var(--hover)`, `var(--success)`, `var(--danger)`, `var(--muted)`). Стиль минималистичный (Linear/Vercel).
- После изменения моделей Django: создать миграцию (`python manage.py makemigrations studio`) и применить (`python manage.py migrate`).
- Промты агентов по умолчанию на английском (`STUDIO_PROMPT_LANG=en`), но видимый пользователю текст (вопросы, summary, instructions) генерируется на русском — это закреплено в самих промтах.

## Таблица коммитов

| № | Сессия | Название | Ключевые файлы | Время |
|---|--------|----------|----------------|-------|
| 1 | 1 | Каталог моделей | `src/studio/models_catalog.py` | 20 мин |
| 2 | 1 | Миграция coder_model → ai_model + поля анти-цикла | `src/studio/models.py`, миграции | 40 мин |
| 3 | 1 | Билинг по tier + resolve_model | `src/studio/billing.py`, `agents/base.py`, `agents/coder.py` | 40 мин |
| 4 | 1 | STUDIO_PROMPT_LANG + pick_prompt | `src/config/settings.py`, `agents/base.py` | 20 мин |
| 5 | 2 | EN промты: Interviewer, Analyst, Planner | `agents/interviewer.py`, `analyst.py`, `planner.py` | 40 мин |
| 6 | 2 | EN промты: Coder, Reviewer, Tester, Fixer | `agents/coder.py`, `reviewer.py`, `tester.py`, `fixer.py` | 40 мин |
| 7 | 3 | Детектор одинакового diff + повторной ошибки | `src/studio/tasks.py` | 50 мин |
| 8 | 3 | Watchdog beat-задача | `tasks.py`, `config/settings.py`, `config/celery.py` | 50 мин |
| 9 | 3 | PipelineSkipView | `views/pipeline.py`, `urls.py`, `serializers.py` | 30 мин |
| 10 | 4 | sandbox.sync_all + dev-server для Next.js | `src/studio/sandbox.py`, `tasks.py` | 50 мин |
| 11 | 4 | Инжект `<base href>` в PreviewProxyView | `views/pipeline.py` | 30 мин |
| 12 | 4 | SSE-события установки зависимостей | `src/studio/tasks.py` | 20 мин |
| 13 | 5 | Компонент PipelineTimeline | `components/studio/PipelineTimeline.tsx`, `StudioLayout.tsx` | 40 мин |
| 14 | 5 | Компонент PipelineRecovery | `components/studio/PipelineRecovery.tsx`, `lib/api/studio.ts` | 40 мин |
| 15 | 5 | UI выбора модели + оценка стоимости | `app/studio/page.tsx`, `lib/api/studio.ts`, `views/projects.py`, `urls.py` | 50 мин |
| 16 | 6 | Компонент StudioHero | `components/studio/StudioHero.tsx`, `app/studio/page.tsx` | 30 мин |
| 17 | 6 | Компонент StackCards | `components/studio/StackCards.tsx`, `app/studio/page.tsx` | 40 мин |
| 18 | 6 | Карточки режимов + интеграция | `app/studio/page.tsx` | 30 мин |
| 19 | 7 | features.ts + FeatureSelector | `lib/studio/features.ts`, `components/studio/FeatureSelector.tsx` | 40 мин |
| 20 | 7 | API принимает selected_features | `serializers.py`, `views/projects.py`, `lib/api/studio.ts` | 30 мин |
| 21 | 7 | Analyst/Planner учитывают features + UI | `agents/analyst.py`, `planner.py`, `app/studio/page.tsx` | 40 мин |
| 22 | 8 | Отключить HMR + перезагрузка iframe | `agents/coder.py`, `components/studio/PreviewPanel.tsx` | 30 мин |
| 23 | 8 | Build-gate перед деплоем | `src/studio/sandbox.py`, `tasks.py` | 30 мин |
| 24 | 8 | Итоговый аудит + .env.example | `.env.example`, общий аудит | 30 мин |

Всего: 24 коммита, 8 сессий.

---

## Сессия 1: Фундамент — модели, поля, язык промтов

Цель: ввести расширяемый каталог из 15 моделей с tier-биллингом, заменить устаревшее поле `coder_model` на `ai_model`, добавить поля состояния для защиты от зацикливания, ввести переключатель языка промтов. После сессии система готова работать с любой моделью из каталога и считать звёзды по её tier.

Коммиты: 1, 2, 3, 4.

### Коммит 1: Каталог моделей

**Файлы**
- Создать: `src/studio/models_catalog.py`

**Что делать**

Создать единый источник правды по доступным моделям Studio. Каталог содержит id (как его понимает провайдер laozhang.ai), человекочитаемый label, category (для UI-группировки) и tier (для биллинга и эскалации). `MODEL_TIER` — производный словарь id → tier. `ESCALATION_MAP` задаёт, на какую smart-модель эскалировать конкретную fast-модель на шагах с тегом `[COMPLEX]` или при повторных ошибках (эскалация в рамках того же вендора).

**Код**

```python
# src/studio/models_catalog.py
"""Каталог моделей Studio: единый источник правды для UI, биллинга и эскалации."""

STUDIO_MODELS = [
    {'id': 'claude-sonnet-4-6',          'label': 'Claude Sonnet 4.6',  'category': 'smart',     'tier': 'smart',  'description': 'Лучший баланс качества и скорости'},
    {'id': 'claude-opus-4-8',            'label': 'Claude Opus 4.8',    'category': 'smart',     'tier': 'smart',  'description': 'Максимальное качество, сложная архитектура'},
    {'id': 'claude-haiku-4-5-20251001',  'label': 'Claude Haiku 4.5',   'category': 'fast',      'tier': 'fast',   'description': 'Быстрый Claude для простых задач'},
    {'id': 'gpt-5',                      'label': 'GPT-5',              'category': 'smart',     'tier': 'smart',  'description': 'Топовый GPT, сильная логика и рефакторинг'},
    {'id': 'gpt-5-mini',                 'label': 'GPT-5 Mini',         'category': 'fast',      'tier': 'fast',   'description': 'Дешёвый GPT-5 для рутинных шагов'},
    {'id': 'gpt-4.1',                    'label': 'GPT-4.1',           'category': 'smart',     'tier': 'smart',  'description': 'Надёжный генералист по коду'},
    {'id': 'gpt-4.1-mini',               'label': 'GPT-4.1 Mini',      'category': 'fast',      'tier': 'fast',   'description': 'Быстрый и дешёвый генералист'},
    {'id': 'gpt-4o',                     'label': 'GPT-4o',            'category': 'fast',      'tier': 'fast',   'description': 'Быстрый мультимодальный'},
    {'id': 'deepseek-v3.2',              'label': 'DeepSeek V3.2',     'category': 'fast',      'tier': 'fast',   'description': 'Сильный код за низкую цену'},
    {'id': 'deepseek-v4-pro',            'label': 'DeepSeek V4 Pro',   'category': 'smart',     'tier': 'smart',  'description': 'Старшая DeepSeek, качество ближе к топу'},
    {'id': 'deepseek-r1',                'label': 'DeepSeek R1',       'category': 'reasoning', 'tier': 'smart',  'description': 'Пошаговые рассуждения, сложная логика'},
    {'id': 'qwen3-coder-plus',           'label': 'Qwen3 Coder Plus',  'category': 'coder',     'tier': 'coder',  'description': 'Специализирован на коде'},
    {'id': 'qwen3-235b-a22b',            'label': 'Qwen3 235B',        'category': 'smart',     'tier': 'smart',  'description': 'Крупная Qwen, сильный генералист'},
    {'id': 'kimi-k2',                    'label': 'Kimi K2',           'category': 'coder',     'tier': 'coder',  'description': 'Длинный контекст, сильна в коде'},
    {'id': 'gemini-2.5-pro',             'label': 'Gemini 2.5 Pro',    'category': 'smart',     'tier': 'smart',  'description': 'Длинный контекст, крупные проекты'},
]

DEFAULT_STUDIO_MODEL = 'claude-sonnet-4-6'

# id -> tier (для биллинга и эскалации)
MODEL_TIER = {m['id']: m['tier'] for m in STUDIO_MODELS}

# Эскалация fast -> smart по вендору для шагов [COMPLEX] и при повторных ошибках.
ESCALATION_MAP = {
    'deepseek-v3.2':             'deepseek-v4-pro',
    'gpt-4.1-mini':              'gpt-4.1',
    'gpt-5-mini':                'gpt-5',
    'gpt-4o':                    'gpt-4.1',
    'claude-haiku-4-5-20251001': 'claude-sonnet-4-6',
}


def is_valid_model(model_id: str) -> bool:
    return model_id in MODEL_TIER
```

**Проверка**: `python -c "from studio.models_catalog import MODEL_TIER; print(MODEL_TIER['gpt-5'])"` выводит `smart`.

### Коммит 2: Миграция coder_model → ai_model + поля анти-цикла

**Файлы**
- Изменить: `src/studio/models.py`
- Создать: миграцию `src/studio/migrations/XXXX_ai_model_and_loop_fields.py` (через `makemigrations`) + data-миграцию

**Что делать**

1. В `StudioProject` добавить поле `ai_model` с дефолтом `'claude-sonnet-4-6'`. Старое поле `coder_model` оставить временно (его удалит data-миграция после переноса данных).
2. В `StudioPipelineState` добавить поля состояния анти-цикла и тайминга.
3. Сгенерировать схемную миграцию, затем добавить data-миграцию: перенос значений `coder_model` → `ai_model` и удаление `coder_model`.

**Код**

В `src/studio/models.py`, класс `StudioProject` (добавить поле рядом с `coder_model`):

```python
    ai_model = models.CharField(max_length=64, default='claude-sonnet-4-6')
    # coder_model сохраняется до применения data-миграции, затем удаляется.
```

В `src/studio/models.py`, класс `StudioPipelineState` (добавить поля):

```python
    last_files_hash = models.CharField(max_length=64, blank=True, default='')
    same_diff_count = models.IntegerField(default=0)
    last_error_signature = models.CharField(max_length=256, blank=True, default='')
    error_repeat_count = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
```

Замечание: поле `error_repeat_count` нужно для коммита 7 (детектор повторной ошибки), добавляем его сразу здесь, чтобы не плодить лишние миграции.

Сгенерировать схемную миграцию:

```bash
cd src && python manage.py makemigrations studio --name ai_model_and_loop_fields
```

Затем создать data-миграцию (отдельный файл) для переноса и удаления `coder_model`:

```python
# src/studio/migrations/XXXX_migrate_coder_model.py
from django.db import migrations


def forwards(apps, schema_editor):
    StudioProject = apps.get_model('studio', 'StudioProject')
    mapping = {'fast': 'deepseek-v3.2', 'smart': 'claude-opus-4-8'}
    for p in StudioProject.objects.all():
        old = getattr(p, 'coder_model', None)
        p.ai_model = mapping.get(old, 'claude-sonnet-4-6')
        p.save(update_fields=['ai_model'])


def backwards(apps, schema_editor):
    StudioProject = apps.get_model('studio', 'StudioProject')
    reverse = {'deepseek-v3.2': 'fast', 'claude-opus-4-8': 'smart'}
    for p in StudioProject.objects.all():
        if hasattr(p, 'coder_model'):
            p.coder_model = reverse.get(p.ai_model, 'fast')
            p.save(update_fields=['coder_model'])


class Migration(migrations.Migration):
    dependencies = [
        ('studio', 'XXXX_ai_model_and_loop_fields'),  # подставить имя миграции из makemigrations
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(model_name='studioproject', name='coder_model'),
    ]
```

После этого удалить определение поля `coder_model` из `models.py`.

**Проверка**: `python manage.py migrate studio` проходит без ошибок; `StudioProject._meta.get_field('ai_model')` существует, `coder_model` — нет.

### Коммит 3: Билинг по tier + resolve_model + эскалация в Coder

**Файлы**
- Изменить: `src/studio/billing.py`
- Изменить: `src/studio/agents/base.py`
- Изменить: `src/studio/agents/coder.py`

**Что делать**

1. В `billing.py` ввести tier `coder` в `STAR_RATE`, привязать `coder_tier_for_model` и `estimate_stars` к `MODEL_TIER`.
2. В `base.py` убрать хардкод `MODEL_FAST`/`MODEL_SMART`, добавить метод `resolve_model()`: для CoderAgent — `project.ai_model`, для остальных агентов — также `project.ai_model` (вся пайплайн-команда работает на выбранной пользователем модели; интервью/анализ/план/ревью получают ту же модель).
3. В `coder.py` `_pick_model()` реализовать эскалацию для `[COMPLEX]`-шагов.

**Код**

В `src/studio/billing.py`:

```python
from .models_catalog import MODEL_TIER

STAR_RATE = {'fast': 1, 'coder': 1.7, 'smart': 3}


def coder_tier_for_model(model: str) -> str:
    return MODEL_TIER.get(model, 'fast')
```

В `estimate_stars()` использовать tier через `MODEL_TIER` (привести к виду):

```python
def estimate_stars(model: str, agent: str = 'coder') -> int:
    tier = MODEL_TIER.get(model, 'fast')
    rate = STAR_RATE[tier]
    base = AGENT_BUDGET.get(agent, 12)
    return int(round(rate * base))
```

(Если в текущей реализации `estimate_stars` имеет другую сигнатуру — сохранить существующую сигнатуру, заменив только источник tier на `MODEL_TIER` и формулу множителя на `STAR_RATE[tier]`.)

В `src/studio/agents/base.py`:

```python
from django.conf import settings
from ..models_catalog import ESCALATION_MAP, MODEL_TIER, DEFAULT_STUDIO_MODEL


class BaseAgent:
    # Удалить: MODEL_FAST = 'deepseek-v3'
    # Удалить: MODEL_SMART = 'claude-opus-4-8'

    def resolve_model(self) -> str:
        """Модель, на которой работает агент. Вся команда использует выбранную пользователем ai_model."""
        model = getattr(self.project, 'ai_model', None)
        return model if model in MODEL_TIER else DEFAULT_STUDIO_MODEL
```

В `src/studio/agents/coder.py`:

```python
from ..models_catalog import ESCALATION_MAP, MODEL_TIER

    def _pick_model(self, step_title: str) -> str:
        base = self.resolve_model()
        if '[COMPLEX]' in (step_title or '') and MODEL_TIER.get(base) == 'fast':
            return ESCALATION_MAP.get(base, base)
        return base
```

Все вызовы `run_prompt(..., model=self.MODEL_FAST/SMART)` заменить на `model=self.resolve_model()` (или `self._pick_model(step_title)` в Coder).

**Проверка**: импорты разрешаются, `estimate_stars('gpt-5')` использует rate=3.

### Коммит 4: STUDIO_PROMPT_LANG + pick_prompt

**Файлы**
- Изменить: `src/config/settings.py`
- Изменить: `src/studio/agents/base.py`

**Что делать**

Ввести переключатель языка системных промтов через env. Хелпер `pick_prompt(ru, en)` возвращает английскую версию по умолчанию.

**Код**

В `src/config/settings.py` (в блоке Studio-настроек):

```python
STUDIO_PROMPT_LANG = os.getenv('STUDIO_PROMPT_LANG', 'en')
```

В `src/studio/agents/base.py` (на уровне модуля):

```python
from django.conf import settings


def pick_prompt(ru: str, en: str) -> str:
    return en if getattr(settings, 'STUDIO_PROMPT_LANG', 'en') == 'en' else ru
```

**Проверка**: `pick_prompt('ру', 'en')` возвращает `'en'` при дефолтных настройках.

---

## Сессия 2: Английские промты для всех агентов

Цель: перевести системные промты всех 7 агентов на английский для повышения качества и стабильности генерации, сохранив русский язык всего пользовательского вывода (вопросы, summary, instructions, комментарии в коде). Каждый агент получает константы `SYSTEM_RU` и `SYSTEM_EN`, выбор через `pick_prompt`.

Коммиты: 5, 6.

### Коммит 5: EN промты — Interviewer, Analyst, Planner

**Файлы**
- Изменить: `src/studio/agents/interviewer.py`
- Изменить: `src/studio/agents/analyst.py`
- Изменить: `src/studio/agents/planner.py`

**Что делать**

В каждом файле объявить константы `SYSTEM_RU` и `SYSTEM_EN` на уровне модуля. В методе агента, где формируется system prompt, заменить хардкод на `pick_prompt(SYSTEM_RU, SYSTEM_EN)` (импортировать `from .base import pick_prompt`).

**Код**

`src/studio/agents/interviewer.py`:

```python
from .base import BaseAgent, pick_prompt

SYSTEM_RU = """Ты интервьюер сервиса генерации веб-приложений. По краткому описанию проекта задай 3-5 умных уточняющих вопросов, которые реально влияют на функционал, дизайн и стек. Не задавай очевидных или избыточных вопросов. Для вопросов с выбором давай 2-4 варианта.
Верни СТРОГО JSON-массив: [{"id":"q1","question":"...","type":"text|choice","options":["..."]}].
Вопросы — на русском. Никакого текста вне JSON."""

SYSTEM_EN = """You are an interviewer for a web-app generation service. Given a short project description, ask 3-5 smart clarifying questions that materially affect scope, design, and stack. Do not ask obvious or redundant questions. Respect the chosen stack (Next.js/React/Vue/HTML). For choice questions provide 2-4 options.
Return STRICTLY a JSON array: [{"id":"q1","question":"...","type":"text|choice","options":["..."]}].
The "question" and "options" text MUST be written in Russian. Output nothing outside the JSON."""
```

В методе `run()` Interviewer: `system = pick_prompt(SYSTEM_RU, SYSTEM_EN)` и передать в `run_prompt(system=system, ...)`.

`src/studio/agents/analyst.py`:

```python
from .base import BaseAgent, pick_prompt

SYSTEM_RU = """Ты системный аналитик. На основе описания проекта и ответов интервью составь технический документ PROJECT.md: цель, целевая аудитория, функциональные требования (нумерованный список), карта страниц, модель данных, стек и обоснование, нефункциональные требования (производительность, адаптив, доступность), ограничения и допущения. Документ должен быть конкретным и реализуемым. Markdown на русском, без преамбулы."""

SYSTEM_EN = """You are a systems analyst. Using the project description and interview answers, produce a technical PROJECT.md document containing: goal, target audience, functional requirements (numbered), page map, data model, chosen stack with justification, non-functional requirements (performance, responsiveness, accessibility), constraints and assumptions. Be concrete and buildable — avoid vague aspirations. Output Markdown in Russian, no preamble."""
```

`src/studio/agents/planner.py`:

```python
from .base import BaseAgent, pick_prompt

SYSTEM_RU = """Ты технический планировщик. На основе PROJECT.md составь COMMITS.md — пошаговый план реализации. Каждый шаг атомарный: заголовок, краткая цель, точный список файлов. Порядок учитывает зависимости. Помечай заголовок тегом [COMPLEX] если шаг включает auth, оплату, интеграции, realtime, миграции БД или затрагивает 5+ файлов. Не превышай 15 шагов. В конце: <STEPS_COUNT>N</STEPS_COUNT>. Markdown на русском, без преамбулы."""

SYSTEM_EN = """You are a technical planner. From PROJECT.md, produce COMMITS.md — a step-by-step implementation plan. Each step is atomic: a heading, a one-line goal, and the exact list of files created/modified. Order by dependency (scaffold first, then components, then integrations). Tag a heading [COMPLEX] if it involves auth, payments, third-party integrations, realtime, DB migrations, or touches 5+ files. Do not exceed 15 steps. End with <STEPS_COUNT>N</STEPS_COUNT>. Output Markdown in Russian, no preamble."""
```

**Проверка**: при `STUDIO_PROMPT_LANG=en` агенты отдают system на английском; вопросы/документы по-прежнему генерируются на русском.

### Коммит 6: EN промты — Coder, Reviewer, Tester, Fixer

**Файлы**
- Изменить: `src/studio/agents/coder.py`
- Изменить: `src/studio/agents/reviewer.py`
- Изменить: `src/studio/agents/tester.py`
- Изменить: `src/studio/agents/fixer.py`

**Что делать**

Аналогично коммиту 5: добавить `SYSTEM_RU`/`SYSTEM_EN`, заменить хардкод на `pick_prompt(SYSTEM_RU, SYSTEM_EN)`.

**Код**

`src/studio/agents/coder.py`:

```python
SYSTEM_RU = """Ты senior-разработчик. Реализуй РОВНО ОДИН шаг из COMMITS.md. Пиши production-ready код: типобезопасный, без TODO, с обработкой ошибок и состояний загрузки. Для Vite: vite.config.ts с server:{host:true,port:3000}. Для Next.js: dev-скрипт "next dev -p 3000 -H 0.0.0.0". Не выдумывай несуществующие зависимости. Не дублируй существующие файлы. Если задан FixPlan — меняй ТОЛЬКО указанные файлы.
Верни СТРОГО JSON: {"files":{"путь":"полное содержимое файла"}}. Полные файлы целиком, не диффы."""

SYSTEM_EN = """You are a senior software engineer. Implement EXACTLY ONE step from COMMITS.md. Write production-ready code: type-safe, no TODO stubs, with error handling and loading states. For Vite projects: vite.config.ts MUST include server:{host:true,port:3000}. For Next.js projects: package.json dev script MUST be "next dev -p 3000 -H 0.0.0.0". Never invent nonexistent dependencies. Respect existing project files (provided in context) — do not duplicate or break them. If a FixPlan is provided, change ONLY the listed files.
Return STRICTLY JSON: {"files":{"relative/path":"full file content"}} — whole files, never diffs. Code comments may be in Russian."""
```

`src/studio/agents/reviewer.py`:

```python
SYSTEM_RU = """Ты ревьюер кода уровня senior. Проверь ТОЛЬКО изменённые файлы. Проверяй: синтаксис и типы, корректность импортов, соответствие шагу, явные баги, БЕЗОПАСНОСТЬ (XSS, инъекции, секреты в коде, dangerouslySetInnerHTML/eval, открытые CORS). severity=error — блокирует; severity=warning — желательно.
Верни СТРОГО JSON: {"passed":bool,"issues":[{"file":"...","severity":"error|warning","message":"..."}],"summary":"..."}. summary — на русском."""

SYSTEM_EN = """You are a senior code reviewer. Review ONLY the changed files. Check: syntax and types, import correctness and paths, conformance to the step, obvious bugs and edge cases, SECURITY (XSS, injection, secrets in code, unsafe dangerouslySetInnerHTML/eval, permissive CORS). severity=error blocks; severity=warning is advisory.
Return STRICTLY JSON: {"passed":bool,"issues":[{"file":"...","severity":"error|warning","message":"..."}],"summary":"..."}. The "summary" and "message" text MUST be in Russian."""
```

`src/studio/agents/tester.py`:

```python
SYSTEM_RU = """Ты QA-инженер. Проанализируй логи сборки из sandbox и exit_code. Определи ошибки компиляции и рантайма. Если exit_code != 0 — build_ok=false.
Верни СТРОГО JSON: {"passed":bool,"errors":[{"type":"build|runtime","message":"...","file":"..."}],"build_ok":bool,"summary":"..."}. summary — на русском."""

SYSTEM_EN = """You are a QA engineer. Analyze the sandbox build/typecheck logs and exit_code. Identify compilation (TS/build) and runtime errors. If exit_code != 0 then build_ok=false.
Return STRICTLY JSON: {"passed":bool,"errors":[{"type":"build|runtime","message":"...","file":"..."}],"build_ok":bool,"summary":"..."}. The "summary" and "message" MUST be in Russian."""
```

`src/studio/agents/fixer.py`:

```python
SYSTEM_RU = """Ты ведущий инженер. Сведи ReviewReport и TestReport в чёткий FixPlan. Сначала — ошибки сборки, затем error-уровня ревью, затем warning. Инструкции конкретные: что именно и в каком файле поправить. Минимизируй target_files.
Верни СТРОГО JSON: {"instructions":"...","target_files":["..."],"priority":"high|medium"}. instructions — на русском."""

SYSTEM_EN = """You are a lead engineer. Merge the ReviewReport and TestReport into a precise FixPlan for the coder. Prioritize: build errors first, then error-severity review issues, then warnings. Instructions must be concrete and actionable: exactly what to change and in which file. Keep target_files minimal (only genuinely affected files).
Return STRICTLY JSON: {"instructions":"...","target_files":["..."],"priority":"high|medium"}. The "instructions" MUST be in Russian."""
```

В каждом методе: `system = pick_prompt(SYSTEM_RU, SYSTEM_EN)`.

**Проверка**: пайплайн проходит на тестовом проекте, JSON-ответы парсятся, пользовательские строки на русском.

---

## Сессия 3: Защита от зацикливания

Цель: исключить бесконечные циклы и зависания пайплайна. Три механизма: детектор одинакового diff (агент не меняет код), детектор повторяющейся ошибки теста (с авто-эскалацией модели), watchdog-задача (тайм-ауты шага и всего пайплайна), а также ручной обход — пропуск шага.

Коммиты: 7, 8, 9.

### Коммит 7: Детектор одинакового diff + повторной ошибки

**Файлы**
- Изменить: `src/studio/tasks.py`

**Что делать**

1. В `coder_iteration` после получения файлов от CoderAgent посчитать стабильный хэш набора файлов. Если хэш совпал с предыдущим — увеличить `same_diff_count`; при достижении 2 — поставить пайплайн в `paused_on_loop` и опубликовать событие `paused`.
2. В `merge_reports` при провале теста сравнить сигнатуру первой ошибки с `last_error_signature`. При повторе ≥2 — эскалировать модель проекта по `ESCALATION_MAP` и опубликовать `escalated`.

**Код**

В начале файла добавить импорт:

```python
import hashlib
```

В `coder_iteration`, сразу после `result = coder.run(...)`:

```python
files = result.get('files', {})
files_hash = hashlib.sha256(
    ''.join(f'{k}:{v}' for k, v in sorted(files.items())).encode()
).hexdigest()[:16]

state = project.pipeline
if files_hash == state.last_files_hash and files_hash:
    state.same_diff_count = (state.same_diff_count or 0) + 1
    if state.same_diff_count >= 2:
        state.status = 'paused_on_loop'
        state.pause_reason = (
            f'Агент не может изменить код на шаге {state.step_index + 1}. '
            f'Опишите, что именно должно измениться.'
        )
        state.save(update_fields=['status', 'pause_reason', 'same_diff_count', 'last_files_hash'])
        publish_event(str(project.id), 'paused', {'reason': state.pause_reason, 'type': 'same_diff'})
        return
else:
    state.same_diff_count = 0

state.last_files_hash = files_hash
state.save(update_fields=['last_files_hash', 'same_diff_count'])
```

В `merge_reports`, после получения `test_report` (где `test_errors` — список ошибок теста):

```python
from .models_catalog import ESCALATION_MAP

state = project.pipeline
first_error = test_errors[0]['message'][:100] if test_errors else ''
if first_error and first_error == state.last_error_signature:
    state.error_repeat_count = (state.error_repeat_count or 0) + 1
    if state.error_repeat_count >= 2:
        escalated = ESCALATION_MAP.get(project.ai_model)
        if escalated:
            project.ai_model = escalated
            project.save(update_fields=['ai_model'])
            publish_event(str(project.id), 'escalated', {'model': escalated})
            state.error_repeat_count = 0
else:
    state.error_repeat_count = 0
state.last_error_signature = first_error
state.save(update_fields=['last_error_signature', 'error_repeat_count'])
```

**Проверка**: при двукратном идентичном выводе CoderAgent пайплайн переходит в `paused_on_loop`; при повторной ошибке теста `project.ai_model` меняется на эскалированную.

### Коммит 8: Watchdog beat-задача

**Файлы**
- Изменить: `src/studio/tasks.py`
- Изменить: `src/config/settings.py`
- Изменить: `src/config/celery.py`

**Что делать**

1. Добавить задачу `watchdog_pipelines`, которая каждые 2 минуты находит зависшие (нет прогресса по шагу > `STUDIO_STEP_STALL_SEC`) и истёкшие (общее время > `STUDIO_PIPELINE_MAX_SEC`) пайплайны, отзывает зависшие задачи и помечает пайплайн как failed (с уборкой sandbox и возвратом резерва).
2. Добавить env-настройки и зарегистрировать задачу в beat.
3. В начале `run_pipeline` проставлять `state.started_at`.

**Код**

В `src/studio/tasks.py`:

```python
@shared_task(name='studio.watchdog_pipelines')
def watchdog_pipelines():
    """Каждые 2 минуты: обнаруживает зависшие и истёкшие пайплайны."""
    from django.utils import timezone
    from celery import current_app

    stall_sec = getattr(settings, 'STUDIO_STEP_STALL_SEC', 240)
    max_sec = getattr(settings, 'STUDIO_PIPELINE_MAX_SEC', 2700)  # 45 минут
    now = timezone.now()

    running = StudioPipelineState.objects.filter(
        status__in=['running']
    ).select_related('project')

    for state in running:
        age_total = (now - state.started_at).total_seconds() if state.started_at else 0
        age_step = (now - state.last_changed).total_seconds() if state.last_changed else 0

        if age_total > max_sec:
            _timeout_pipeline(state, 'Пайплайн превысил максимальное время выполнения')
        elif age_step > stall_sec:
            if state.current_task_id:
                try:
                    current_app.control.revoke(state.current_task_id, terminate=True, signal='SIGTERM')
                except Exception:
                    pass
            _timeout_pipeline(
                state,
                f'Агент завис на шаге {state.step_index + 1} (нет ответа > {stall_sec // 60} мин)',
            )


def _timeout_pipeline(state, reason):
    from .sandbox import kill_sandbox
    from .billing import release_reserve

    project = state.project
    state.status = 'failed'
    state.pause_reason = reason
    state.save(update_fields=['status', 'pause_reason'])
    project.status = 'failed'
    project.save(update_fields=['status'])
    if project.sandbox_container_id:
        try:
            kill_sandbox(project.sandbox_container_id)
        except Exception:
            pass
        project.sandbox_container_id = ''
        project.save(update_fields=['sandbox_container_id'])
    try:
        release_reserve(project)
    except Exception:
        pass
    publish_event(str(project.id), 'failed', {'reason': reason})
```

Примечание: поле тайминга последнего изменения шага — `StudioPipelineState.last_changed` (auto_now). Если в проекте используется `updated_at` — заменить на него. Не вводить новое поле.

В `src/studio/tasks.py`, в начале `run_pipeline`:

```python
from django.utils import timezone
state.started_at = timezone.now()
state.save(update_fields=['started_at'])
```

В `src/config/settings.py`:

```python
STUDIO_STEP_STALL_SEC = int(os.getenv('STUDIO_STEP_STALL_SEC', '240'))
STUDIO_PIPELINE_MAX_SEC = int(os.getenv('STUDIO_PIPELINE_MAX_SEC', '2700'))
```

В `src/config/celery.py`, в `beat_schedule`:

```python
'studio-watchdog': {
    'task': 'studio.watchdog_pipelines',
    'schedule': 120.0,  # каждые 2 минуты
},
```

**Проверка**: при искусственном зависании шага watchdog через ~2-4 мин отзывает задачу и переводит пайплайн в `failed`, sandbox убран, резерв возвращён.

### Коммит 9: PipelineSkipView — пропуск шага

**Файлы**
- Изменить: `src/studio/views/pipeline.py`
- Изменить: `src/studio/urls.py`
- Изменить: `src/studio/serializers.py`

**Что делать**

Добавить view, которое сбрасывает состояние анти-цикла и запускает следующий шаг. Расширить сериализатор состояния пайплайна полями для UI восстановления.

**Код**

В `src/studio/views/pipeline.py`:

```python
class PipelineSkipView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        state = project.pipeline
        state.status = 'running'
        state.pause_requested = False
        state.same_diff_count = 0
        state.last_files_hash = ''
        state.last_error_signature = ''
        state.error_repeat_count = 0
        state.save(update_fields=[
            'status', 'pause_requested', 'same_diff_count',
            'last_files_hash', 'last_error_signature', 'error_repeat_count',
        ])
        project.status = 'coding'
        project.save(update_fields=['status'])
        from ..tasks import next_step
        next_step.delay(str(project.id), state.step_index)
        publish_event(str(project.id), 'resumed', {'action': 'skip_step'})
        return Response({'status': 'running', 'skipped_step': state.step_index})
```

В `src/studio/urls.py` (добавить путь и импорт `PipelineSkipView`):

```python
path('projects/<uuid:id>/pipeline/skip/', PipelineSkipView.as_view()),
```

В `src/studio/serializers.py` расширить `PipelineStateSerializer`:

```python
from django.conf import settings


class PipelineStateSerializer(serializers.ModelSerializer):
    max_iterations = serializers.SerializerMethodField()

    class Meta:
        model = StudioPipelineState
        fields = [
            'status', 'step_index', 'iteration_count', 'max_iterations',
            'pause_reason', 'same_diff_count', 'current_task_id',
            # ... существующие поля
        ]

    def get_max_iterations(self, obj):
        return getattr(settings, 'STUDIO_MAX_ITERATIONS', 5)
```

(Если константа `STUDIO_MAX_ITERATIONS` отсутствует — добавить её в `settings.py`: `STUDIO_MAX_ITERATIONS = int(os.getenv('STUDIO_MAX_ITERATIONS', '5'))`.)

**Проверка**: `POST /api/v1/studio/projects/<id>/pipeline/skip/` сбрасывает счётчики и запускает следующий шаг; сериализатор отдаёт `max_iterations`.

---

## Сессия 4: Фиксы превью — блокеры

Цель: устранить главные причины неработающего превью — рассинхрон файлов БД и контейнера, неправильный запуск dev-сервера для Next.js, ломаные относительные пути в fallback-превью, отсутствие обратной связи во время долгой установки зависимостей.

Коммиты: 10, 11, 12.

### Коммит 10: sandbox.sync_all + dev-server для Next.js

**Файлы**
- Изменить: `src/studio/sandbox.py`
- Изменить: `src/studio/tasks.py`

**Что делать**

1. Добавить `sync_all(project)` — записывает все `StudioFile` проекта в контейнер.
2. Переписать `start_dev_server` так, чтобы он определял Next.js по dev-скрипту и запускал его с `-H 0.0.0.0`, для Vite — с `--host 0.0.0.0`, иначе fallback на `http.server`.
3. Доработать `wait_for_ready` (warmup-запрос для триггера компиляции Next.js, увеличенный timeout).
4. В `restart_preview` и при первичном поднятии sandbox вызывать `sandbox.sync_all(project)` после записи файлов.

**Код**

В `src/studio/sandbox.py`:

```python
def sync_all(project) -> None:
    """Записывает все StudioFile проекта в sandbox-контейнер."""
    cid = project.sandbox_container_id
    if not cid:
        return
    files = {f.path: f.content for f in project.files.all()}
    if files:
        write_files(cid, files)


def start_dev_server(container_id: str) -> int:
    import json as _json
    client = get_docker()

    _, pkg_raw = exec_command(container_id, 'cat /workspace/package.json 2>/dev/null || echo {}')
    try:
        pkg = _json.loads(pkg_raw)
        scripts = pkg.get('scripts', {})
        has_dev = 'dev' in scripts
        dev_script = scripts.get('dev', '')
        is_next = 'next' in dev_script
    except Exception:
        has_dev = False
        is_next = False

    if has_dev:
        if is_next:
            cmd = ['sh', '-c', 'pnpm dev -- -p 3000 -H 0.0.0.0 > /tmp/dev.log 2>&1']
        else:
            cmd = ['sh', '-c', 'pnpm dev --port 3000 --host 0.0.0.0 > /tmp/dev.log 2>&1']
    else:
        cmd = ['sh', '-c', 'python3 -m http.server 3000 --bind 0.0.0.0 > /tmp/dev.log 2>&1']

    exec_id = client.api.exec_create(container_id, cmd, workdir='/workspace')
    client.api.exec_start(exec_id, detach=True)
    return 3000


def wait_for_ready(container_id: str, timeout: int = 150, warmup: bool = False) -> bool:
    import time
    if warmup:
        # Триггерим компиляцию Next.js первым запросом
        exec_command(container_id, 'curl -s http://localhost:3000/ > /dev/null 2>&1 || true')
    for _ in range(timeout // 3):
        if is_http_alive(container_id):
            return True
        time.sleep(3)
    return False
```

Примечание: `is_http_alive(container_id)` — существующая функция проверки порта 3000. Если её сигнатура отличается — сохранить существующий способ проверки внутри цикла, изменив только timeout и добавив warmup.

В `src/studio/tasks.py`, в `restart_preview` и в функции поднятия sandbox (`_ensure_sandbox`/аналог), после `write_files`/первичной записи файлов:

```python
sandbox.sync_all(project)
```

И при ожидании Next.js вызывать `sandbox.wait_for_ready(cid, timeout=150, warmup=True)` для стека `nextjs`.

**Проверка**: для Next.js-проекта превью поднимается на 0.0.0.0:3000 и отвечает 200 после warmup; для Vite — `--host` присутствует; файлы из БД синхронизированы в контейнер.

### Коммит 11: Инжект `<base href>` в PreviewProxyView

**Файлы**
- Изменить: `src/studio/views/pipeline.py`

**Что делать**

В fallback-ветке `PreviewProxyView.get()` (когда нет sandbox и отдаём файл напрямую из БД) для HTML-ответов инжектировать `<base href>`, чтобы относительные пути (css/js/img) резолвились через прокси-префикс.

**Код**

В `PreviewProxyView.get()`, при отдаче файла из БД:

```python
if content_type.startswith('text/html'):
    base_href = f'/api/v1/studio/projects/{id}/preview/'
    base_tag = f'<base href="{base_href}">'
    content = file_obj.content
    if '<head>' in content:
        content = content.replace('<head>', f'<head>{base_tag}', 1)
    elif '<html>' in content:
        content = content.replace('<html>', f'<html><head>{base_tag}</head>', 1)
    else:
        content = base_tag + content
    resp = HttpResponse(content, content_type=content_type)
else:
    resp = HttpResponse(file_obj.content, content_type=content_type)
resp['X-Frame-Options'] = 'SAMEORIGIN'
return resp
```

**Проверка**: статический HTML-проект в превью корректно подгружает относительные css/js.

### Коммит 12: SSE-события установки зависимостей

**Файлы**
- Изменить: `src/studio/tasks.py`

**Что делать**

Обернуть вызов `sandbox.install_deps(cid)` в события `progress` (старт и завершение), чтобы фронт показывал пользователю, что идёт установка (1-3 минуты).

**Код**

```python
publish_event(str(project.id), 'progress', {
    'agent': 'sandbox',
    'message': 'Устанавливаю зависимости (может занять 1-3 минуты)...',
    'step': 'install_deps',
})
exit_code, output = sandbox.install_deps(cid)
publish_event(str(project.id), 'progress', {
    'agent': 'sandbox',
    'message': 'Зависимости установлены' if exit_code == 0 else f'Ошибка установки: {output[-200:]}',
    'step': 'install_deps_done',
})
```

**Проверка**: в SSE-потоке появляются события `progress` со `step: install_deps` и `install_deps_done`.

---

## Сессия 5: Превью UI + модели

Цель: дать пользователю видимый прогресс пайплайна, средства восстановления при паузе и осознанный выбор модели с оценкой стоимости.

Коммиты: 13, 14, 15.

### Коммит 13: Компонент PipelineTimeline

**Файлы**
- Создать: `frontend/components/studio/PipelineTimeline.tsx`
- Изменить: `frontend/components/studio/StudioLayout.tsx`

**Что делать**

Создать компонент таймлайна шагов с индикаторами статуса, текущим агентом (человекочитаемая подпись) и счётчиком попыток. Подключить в `StudioLayout`, передав данные из polling/SSE pipeline-статуса.

**Код**

```tsx
// frontend/components/studio/PipelineTimeline.tsx
"use client";
import { Check, Loader2, Circle, AlertCircle } from "lucide-react";

interface Step {
  title: string;
  status: "done" | "active" | "waiting" | "error";
}

interface PipelineTimelineProps {
  steps: Step[];
  currentAgent: string;
  iterationCount: number;
  maxIterations: number;
  elapsedSeconds: number;
}

const AGENT_LABELS: Record<string, string> = {
  analyst: "Разбираю, что нужно построить",
  planner: "Составляю план по шагам",
  coder: "Пишу код",
  reviewer: "Проверяю код на ошибки",
  tester: "Запускаю сборку",
  fixer: "Готовлю исправления",
  sandbox: "Запускаю среду разработки",
  interviewer: "Уточняю детали проекта",
};

export function PipelineTimeline({ steps, currentAgent, iterationCount, maxIterations, elapsedSeconds }: PipelineTimelineProps) {
  return (
    <div className="space-y-1">
      {currentAgent && (
        <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)] mb-3 px-1">
          <Loader2 size={14} className="animate-spin shrink-0" />
          <span>{AGENT_LABELS[currentAgent] ?? currentAgent}</span>
          {iterationCount > 0 && (
            <span className="text-xs text-[var(--muted)] ml-auto shrink-0">
              Попытка {iterationCount + 1} из {maxIterations}
            </span>
          )}
        </div>
      )}
      {steps.map((step, i) => (
        <div key={i} className="flex items-start gap-2 py-1 px-1 rounded text-sm">
          <div className="mt-0.5 shrink-0">
            {step.status === "done" && <Check size={14} className="text-[var(--success)]" />}
            {step.status === "active" && <Loader2 size={14} className="animate-spin text-[var(--text-secondary)]" />}
            {step.status === "waiting" && <Circle size={14} className="text-[var(--muted)] opacity-40" />}
            {step.status === "error" && <AlertCircle size={14} className="text-[var(--danger)]" />}
          </div>
          <span className={step.status === "waiting" ? "text-[var(--text-secondary)] opacity-50" : "text-[var(--text)]"}>
            {step.title}
          </span>
          {step.status === "active" && elapsedSeconds > 5 && (
            <span className="ml-auto text-xs text-[var(--muted)] shrink-0">{elapsedSeconds}с</span>
          )}
        </div>
      ))}
    </div>
  );
}
```

В `StudioLayout.tsx`: импортировать `PipelineTimeline`, разместить в боковой/нижней панели, передать `steps` (из плана + текущего step_index), `currentAgent`, `iterationCount`, `maxIterations` (из pipeline-статуса), `elapsedSeconds` (локальный таймер с момента старта шага).

**Проверка**: при работе пайплайна виден список шагов с активным индикатором и подписью текущего агента.

### Коммит 14: Компонент PipelineRecovery

**Файлы**
- Создать: `frontend/components/studio/PipelineRecovery.tsx`
- Изменить: `frontend/lib/api/studio.ts`

**Что делать**

Создать панель восстановления при паузе пайплайна: показывает причину, при типе `same_diff` — textarea с подсказкой, кнопки «Попробовать снова», «Пропустить шаг». Добавить методы `skipStep` и `resumePipeline` в API-клиент.

**Код**

```tsx
// frontend/components/studio/PipelineRecovery.tsx
"use client";
import { useState } from "react";
import { AlertCircle, RefreshCw, SkipForward } from "lucide-react";
import { studioApi } from "@/lib/api/studio";

interface PipelineRecoveryProps {
  projectId: string;
  reason: string;
  recoveryType: "loop" | "same_diff" | "failed" | "no_funds" | "manual";
  onResume: () => void;
}

export function PipelineRecovery({ projectId, reason, recoveryType, onResume }: PipelineRecoveryProps) {
  const [hint, setHint] = useState("");
  const [loading, setLoading] = useState<string | null>(null);

  const handleResume = async (action: "continue" | "skip_step" | "with_hint") => {
    setLoading(action);
    try {
      if (action === "skip_step") {
        await studioApi.skipStep(projectId);
      } else {
        await studioApi.resumePipeline(projectId, { action, hint: action === "with_hint" ? hint : undefined });
      }
      onResume();
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="rounded-lg border border-[var(--danger)] bg-[var(--card-bg)] p-4 space-y-3">
      <div className="flex items-start gap-2">
        <AlertCircle size={16} className="text-[var(--danger)] mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-medium">Генерация приостановлена</p>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">{reason}</p>
        </div>
      </div>

      {recoveryType === "same_diff" && (
        <textarea
          value={hint}
          onChange={e => setHint(e.target.value)}
          placeholder="Опишите, что именно должно измениться..."
          rows={3}
          className="w-full text-sm rounded border border-[var(--border)] bg-[var(--bg)] p-2 resize-none"
        />
      )}

      <div className="flex gap-2">
        <button
          onClick={() => handleResume(recoveryType === "same_diff" && hint ? "with_hint" : "continue")}
          disabled={!!loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading === "continue" ? "animate-spin" : ""} />
          Попробовать снова
        </button>
        <button
          onClick={() => handleResume("skip_step")}
          disabled={!!loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm border border-[var(--border)] hover:bg-[var(--hover)] disabled:opacity-50"
        >
          <SkipForward size={14} />
          Пропустить шаг
        </button>
      </div>
    </div>
  );
}
```

В `frontend/lib/api/studio.ts`:

```ts
skipStep: async (projectId: string) => {
  const res = await fetch(`${API_URL}/studio/projects/${projectId}/pipeline/skip/`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("skip failed");
  return res.json();
},

resumePipeline: async (projectId: string, opts: { action: string; hint?: string }) => {
  const res = await fetch(`${API_URL}/studio/projects/${projectId}/pipeline/resume/`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(opts),
  });
  if (!res.ok) throw new Error("resume failed");
  return res.json();
},
```

Примечание: `authHeaders()` — существующий хелпер авторизации в `studio.ts`. Эндпоинт resume (`pipeline/resume/`) уже существует (`PipelineResumeView`); если он не принимает `action`/`hint` — расширить его обработку этих полей.

**Проверка**: при паузе `same_diff` показывается textarea; кнопки вызывают соответствующие API и возобновляют пайплайн.

### Коммит 15: UI выбора модели + оценка стоимости

**Файлы**
- Изменить: `frontend/app/studio/page.tsx`
- Изменить: `frontend/lib/api/studio.ts`
- Изменить: `src/studio/views/projects.py`
- Изменить: `src/studio/urls.py`

**Что делать**

1. Backend: view `ModelsCatalogView`, отдающий `STUDIO_MODELS`; роут `models/`.
2. Frontend: метод `getModels`, тип `StudioModel`; в форме создания — `<select>` с `<optgroup>` по category и строка оценки `≈ N звёзд за шаг` (tier→STAR_RATE×12).

**Код**

В `src/studio/views/projects.py`:

```python
class ModelsCatalogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from ..models_catalog import STUDIO_MODELS
        return Response(STUDIO_MODELS)
```

В `src/studio/urls.py` (импортировать `ModelsCatalogView`):

```python
path('models/', ModelsCatalogView.as_view()),
```

В `frontend/lib/api/studio.ts`:

```ts
export interface StudioModel {
  id: string;
  label: string;
  category: "smart" | "fast" | "coder" | "reasoning";
  tier: "smart" | "fast" | "coder";
  description: string;
}

// внутри studioApi:
getModels: async (): Promise<StudioModel[]> => {
  const res = await fetch(`${API_URL}/studio/models/`, { headers: authHeaders() });
  return res.json();
},
```

В `frontend/app/studio/page.tsx`:

```tsx
const STAR_RATE: Record<string, number> = { fast: 1, coder: 1.7, smart: 3 };
const CATEGORY_LABELS: Record<string, string> = {
  smart: "Smart — максимальное качество",
  fast: "Fast — быстро и дёшево",
  coder: "Coder — заточены под код",
  reasoning: "Reasoning — глубокие рассуждения",
};

const [aiModel, setAiModel] = useState("claude-sonnet-4-6");
const { data: models = [] } = useQuery({ queryKey: ["studio-models"], queryFn: studioApi.getModels });

const selected = models.find(m => m.id === aiModel);
const starsPerStep = selected ? Math.round(STAR_RATE[selected.tier] * 12) : 12;

const grouped = ["smart", "fast", "coder", "reasoning"].map(cat => ({
  cat,
  items: models.filter(m => m.category === cat),
})).filter(g => g.items.length > 0);
```

JSX:

```tsx
<div>
  <label className="text-sm font-medium mb-1.5 block">Модель</label>
  <select
    value={aiModel}
    onChange={e => setAiModel(e.target.value)}
    className="w-full text-sm rounded border border-[var(--border)] bg-[var(--bg)] p-2"
  >
    {grouped.map(g => (
      <optgroup key={g.cat} label={CATEGORY_LABELS[g.cat] ?? g.cat}>
        {g.items.map(m => (
          <option key={m.id} value={m.id}>{m.label} — {m.description}</option>
        ))}
      </optgroup>
    ))}
  </select>
  <p className="text-xs text-[var(--muted)] mt-1">≈ {starsPerStep} звёзд за шаг</p>
</div>
```

Прокинуть `ai_model: aiModel` в payload `createMutation`.

**Проверка**: список моделей сгруппирован по category; смена модели обновляет оценку звёзд; проект создаётся с выбранной `ai_model`.

---

## Сессия 6: Studio Landing — онбординг

Цель: превратить пустую страницу Studio в понятный онбординг — hero с тремя шагами, карточки стеков с реалистичными ожиданиями по превью, карточки режимов.

Коммиты: 16, 17, 18.

### Коммит 16: Компонент StudioHero

**Файлы**
- Создать: `frontend/components/studio/StudioHero.tsx`
- Изменить: `frontend/app/studio/page.tsx`

**Что делать**

Создать hero-блок с заголовком, подзаголовком, тремя шагами-карточками и CTA. Показывать его, когда форма скрыта и у пользователя нет проектов.

**Код**

```tsx
// frontend/components/studio/StudioHero.tsx
"use client";
import { MessageSquare, Cpu, Eye, ChevronRight } from "lucide-react";

interface StudioHeroProps {
  onStart: () => void;
}

const STEPS = [
  { icon: MessageSquare, title: "Опишите идею", desc: "Расскажите, что хотите создать, словами на русском" },
  { icon: Cpu, title: "Агенты пишут код", desc: "7 AI-агентов планируют, кодят и проверяют за вас" },
  { icon: Eye, title: "Смотрите и публикуйте", desc: "Живое превью, правки по запросу, публикация в один клик" },
];

export function StudioHero({ onStart }: StudioHeroProps) {
  return (
    <div className="mb-10">
      <h2 className="text-3xl font-semibold tracking-tight mb-3">
        Создайте сайт или приложение,<br />просто описав идею
      </h2>
      <p className="text-[var(--text-secondary)] text-base mb-8 max-w-xl">
        Studio — команда AI-агентов, которая проектирует, пишет и проверяет код за вас.
        Без знания программирования. Без VPN. Оплата в рублях.
      </p>
      <div className="grid grid-cols-3 gap-4 mb-8">
        {STEPS.map((step, i) => (
          <div key={i} className="flex flex-col gap-2 p-4 rounded-lg border border-[var(--border)] bg-[var(--card-bg)]">
            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--muted)] font-mono">{i + 1}</span>
              <step.icon size={16} className="text-[var(--text-secondary)]" />
            </div>
            <p className="font-medium text-sm">{step.title}</p>
            <p className="text-xs text-[var(--text-secondary)]">{step.desc}</p>
          </div>
        ))}
      </div>
      <button
        onClick={onStart}
        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
      >
        Создать проект
        <ChevronRight size={16} />
      </button>
    </div>
  );
}
```

В `frontend/app/studio/page.tsx`: импортировать и отрендерить `<StudioHero onStart={() => setShowForm(true)} />` при условии `!showForm && projects.length === 0`.

**Проверка**: новый пользователь видит hero; клик по CTA открывает форму.

### Коммит 17: Компонент StackCards

**Файлы**
- Создать: `frontend/components/studio/StackCards.tsx`
- Изменить: `frontend/app/studio/page.tsx`

**Что делать**

Заменить `<select>` стека на карточки с описанием, плюсами и реалистичной заметкой о времени первого превью.

**Код**

```tsx
// frontend/components/studio/StackCards.tsx
"use client";
import { FileCode, Atom, Layers, Boxes } from "lucide-react";

interface StackCardProps {
  selected: string;
  onSelect: (stack: string) => void;
}

const STACKS = [
  {
    value: "html",
    icon: FileCode,
    label: "HTML",
    subtitle: "Лендинги, промо, визитки",
    pros: ["Мгновенное превью", "Не нужен Node.js", "Max совместимость"],
    previewNote: "Превью открывается сразу из файлов",
  },
  {
    value: "react",
    icon: Atom,
    label: "React",
    subtitle: "SPA, дашборды, формы",
    pros: ["Богатые UI-компоненты", "Hooks", "Огромная экосистема"],
    previewNote: "Первый запуск ~2-3 мин (установка зависимостей)",
  },
  {
    value: "vue",
    icon: Layers,
    label: "Vue",
    subtitle: "Средние SPA",
    pros: ["Проще синтаксис", "Плавный старт"],
    previewNote: "Первый запуск ~2-3 мин (установка зависимостей)",
  },
  {
    value: "nextjs",
    icon: Boxes,
    label: "Next.js",
    subtitle: "Полноценные приложения",
    pros: ["SEO из коробки", "API routes", "Деплой на Vercel"],
    previewNote: "Первый запуск ~3-5 мин",
  },
];

export function StackCards({ selected, onSelect }: StackCardProps) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {STACKS.map((s) => (
        <button
          key={s.value}
          type="button"
          onClick={() => onSelect(s.value)}
          className={`text-left p-3 rounded-lg border transition-colors ${
            selected === s.value
              ? "border-blue-500 bg-blue-600/10"
              : "border-[var(--border)] hover:border-[var(--text-secondary)]"
          }`}
        >
          <div className="flex items-center gap-2 mb-1.5">
            <s.icon size={14} className={selected === s.value ? "text-blue-400" : "text-[var(--text-secondary)]"} />
            <span className="font-medium text-sm">{s.label}</span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] mb-1.5">{s.subtitle}</p>
          <ul className="space-y-0.5 mb-1.5">
            {s.pros.map((p) => (
              <li key={p} className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
                <span className="text-[var(--success)]">+</span> {p}
              </li>
            ))}
          </ul>
          <p className="text-xs text-[var(--muted)]">{s.previewNote}</p>
        </button>
      ))}
    </div>
  );
}
```

В `frontend/app/studio/page.tsx`: заменить `<select>` стека на `<StackCards selected={stack} onSelect={setStack} />`.

**Проверка**: стек выбирается карточкой, значение `stack` обновляется, форма отправляет корректное значение.

### Коммит 18: Карточки режимов + интеграция

**Файлы**
- Изменить: `frontend/app/studio/page.tsx`

**Что делать**

Обновить `MODE_OPTIONS` (добавить описания и иконки), заменить кнопки режимов на карточки. Убедиться, что Hero и StackCards интегрированы (из коммитов 16-17).

**Код**

```tsx
import { Zap, StepForward, Hand } from "lucide-react";

const MODE_OPTIONS = [
  { value: "auto",   label: "Авто",       icon: Zap,         desc: "Агенты делают всё сами — вы только описываете. Самый быстрый путь." },
  { value: "semi",   label: "Полу-авто",  icon: StepForward, desc: "Подтверждаете каждый шаг — видите прогресс, останавливаетесь когда нужно." },
  { value: "manual", label: "Ручной",     icon: Hand,        desc: "Полный контроль: одобряете каждый файл. Для тех, кто хочет вникать." },
];
```

JSX (замена кнопок режимов):

```tsx
<div className="grid grid-cols-3 gap-2">
  {MODE_OPTIONS.map((opt) => (
    <button key={opt.value} type="button" onClick={() => setMode(opt.value)}
      className={`p-3 rounded-lg border text-left transition-colors ${
        mode === opt.value ? "border-blue-500 bg-blue-600/10" : "border-[var(--border)] hover:border-[var(--text-secondary)]"
      }`}>
      <div className="flex items-center gap-1.5 mb-1">
        <opt.icon size={13} className={mode === opt.value ? "text-blue-400" : "text-[var(--text-secondary)]"} />
        <span className="text-sm font-medium">{opt.label}</span>
      </div>
      <p className="text-xs text-[var(--text-secondary)]">{opt.desc}</p>
    </button>
  ))}
</div>
```

**Проверка**: режим выбирается карточкой; значения `auto`/`semi`/`manual` корректно сохраняются и уходят в API.

---

## Сессия 7: Выбор фич вместо шаблонов

Цель: заменить жёсткие шаблоны на гибкий выбор функций (chips по категориям). Выбранные фичи сохраняются в `interview_data` и учитываются Analyst и Planner как обязательные требования.

Коммиты: 19, 20, 21.

### Коммит 19: features.ts + FeatureSelector

**Файлы**
- Создать: `frontend/lib/studio/features.ts`
- Создать: `frontend/components/studio/FeatureSelector.tsx`

**Что делать**

Описать каталог фич с категориями и компонент-селектор chips с группировкой, кнопкой сброса и счётчиком.

**Код**

```ts
// frontend/lib/studio/features.ts
export interface Feature {
  id: string;
  label: string;
  category: string;
}

export const FEATURE_CATEGORIES = [
  { key: "nav", label: "Навигация" },
  { key: "content", label: "Контент" },
  { key: "forms", label: "Формы" },
  { key: "ecom", label: "E-commerce" },
  { key: "auth", label: "Авторизация" },
  { key: "extra", label: "Дополнительно" },
  { key: "integrations", label: "Интеграции" },
];

export const ALL_FEATURES: Feature[] = [
  { id: "header_menu", label: "Header с меню", category: "nav" },
  { id: "footer", label: "Footer", category: "nav" },
  { id: "breadcrumbs", label: "Breadcrumbs", category: "nav" },
  { id: "sidebar", label: "Sidebar", category: "nav" },
  { id: "hero", label: "Hero-секция", category: "content" },
  { id: "gallery", label: "Галерея / карточки", category: "content" },
  { id: "blog", label: "Блог / статьи", category: "content" },
  { id: "faq", label: "FAQ-раздел", category: "content" },
  { id: "reviews", label: "Отзывы", category: "content" },
  { id: "contact_form", label: "Форма обратной связи", category: "forms" },
  { id: "booking_form", label: "Форма записи / бронирования", category: "forms" },
  { id: "order_form", label: "Форма заказа", category: "forms" },
  { id: "quiz", label: "Квиз", category: "forms" },
  { id: "cart", label: "Корзина", category: "ecom" },
  { id: "catalog", label: "Каталог товаров", category: "ecom" },
  { id: "product_card", label: "Карточка товара", category: "ecom" },
  { id: "checkout", label: "Чекаут", category: "ecom" },
  { id: "auth", label: "Регистрация / вход", category: "auth" },
  { id: "account", label: "Личный кабинет", category: "auth" },
  { id: "profile", label: "Профиль пользователя", category: "auth" },
  { id: "dark_mode", label: "Тёмная тема", category: "extra" },
  { id: "animations", label: "Анимации", category: "extra" },
  { id: "responsive", label: "Адаптив мобильный", category: "extra" },
  { id: "i18n", label: "Мультиязычность", category: "extra" },
  { id: "search", label: "Поиск по странице", category: "extra" },
  { id: "yandex_maps", label: "Яндекс.Карты", category: "integrations" },
  { id: "telegram_btn", label: "Telegram-кнопка", category: "integrations" },
  { id: "whatsapp_btn", label: "WhatsApp-кнопка", category: "integrations" },
  { id: "instagram", label: "Instagram-ссылки", category: "integrations" },
];
```

```tsx
// frontend/components/studio/FeatureSelector.tsx
"use client";
import { ALL_FEATURES, FEATURE_CATEGORIES } from "@/lib/studio/features";

interface FeatureSelectorProps {
  selected: string[];
  onChange: (ids: string[]) => void;
}

export function FeatureSelector({ selected, onChange }: FeatureSelectorProps) {
  const toggle = (id: string) => {
    onChange(selected.includes(id) ? selected.filter(x => x !== id) : [...selected, id]);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium">Выберите нужные функции</label>
        {selected.length > 0 && (
          <button type="button" onClick={() => onChange([])} className="text-xs text-[var(--text-secondary)] hover:text-[var(--text)]">
            Сбросить ({selected.length})
          </button>
        )}
      </div>
      {FEATURE_CATEGORIES.map(cat => {
        const items = ALL_FEATURES.filter(f => f.category === cat.key);
        return (
          <div key={cat.key}>
            <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wide mb-1.5">{cat.label}</p>
            <div className="flex flex-wrap gap-1.5">
              {items.map(f => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => toggle(f.id)}
                  className={`px-2.5 py-1 rounded text-xs border transition-colors ${
                    selected.includes(f.id)
                      ? "border-blue-500 bg-blue-600/15 text-blue-300"
                      : "border-[var(--border)] hover:border-[var(--text-secondary)] text-[var(--text-secondary)]"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

**Проверка**: chips переключаются, сброс работает, счётчик корректен.

### Коммит 20: API принимает selected_features

**Файлы**
- Изменить: `src/studio/serializers.py`
- Изменить: `src/studio/views/projects.py`
- Изменить: `frontend/lib/api/studio.ts`

**Что делать**

Сериализатор создания проекта принимает `selected_features` (write-only список строк). View извлекает их из validated_data и сохраняет в `interview_data['features']`. Тип payload на фронте расширяется.

**Код**

В `src/studio/serializers.py` (сериализатор создания проекта):

```python
selected_features = serializers.ListField(
    child=serializers.CharField(), required=False, default=list, write_only=True
)
```

Добавить `selected_features` в `Meta.fields`.

В `src/studio/views/projects.py` (метод создания, после валидации):

```python
selected_features = serializer.validated_data.pop('selected_features', [])
project = StudioProject.objects.create(**serializer.validated_data, user=request.user)
if selected_features:
    project.interview_data = project.interview_data or {}
    project.interview_data['features'] = selected_features
    project.save(update_fields=['interview_data'])
```

(Если создание идёт через `serializer.save(user=...)` — переопределить `create()` в сериализаторе, изъяв `selected_features` перед `StudioProject.objects.create`, и записав фичи в `interview_data` объекта.)

В `frontend/lib/api/studio.ts`, тип `CreateProjectPayload`:

```ts
selected_features?: string[];
```

**Проверка**: POST с `selected_features` создаёт проект с `interview_data.features`.

### Коммит 21: Analyst/Planner учитывают features + UI

**Файлы**
- Изменить: `src/studio/agents/analyst.py`
- Изменить: `src/studio/agents/planner.py`
- Изменить: `frontend/app/studio/page.tsx`

**Что делать**

Analyst и Planner подмешивают выбранные фичи в user-сообщение как обязательные требования. На фронте — подключить `FeatureSelector` в форму «С нуля» и прокинуть `selected_features` в мутацию создания.

**Код**

В `src/studio/agents/analyst.py`, при формировании `user_msg`:

```python
features = (project.interview_data or {}).get('features', [])
if features:
    features_text = '\n'.join(f'- {f}' for f in features)
    user_msg += (
        f'\n\nОБЯЗАТЕЛЬНЫЕ ФУНКЦИИ (выбраны пользователем):\n{features_text}\n'
        f'Включи все эти функции в функциональные требования PROJECT.md.'
    )
```

В `src/studio/agents/planner.py`:

```python
features = (project.interview_data or {}).get('features', [])
if features:
    features_text = '\n'.join(f'- {f}' for f in features)
    user_msg += (
        f'\n\nMUST-HAVE компоненты (выбраны пользователем, обязательны):\n{features_text}\n'
        f'Каждая функция должна быть покрыта хотя бы одним шагом COMMITS.md.'
    )
```

В `frontend/app/studio/page.tsx`:

```tsx
import { FeatureSelector } from "@/components/studio/FeatureSelector";

const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);

// В форме "С нуля":
<FeatureSelector selected={selectedFeatures} onChange={setSelectedFeatures} />

// В payload createMutation:
selected_features: selectedFeatures,
```

**Проверка**: выбранные фичи доходят до Analyst/Planner и появляются в требованиях/шагах плана.

---

## Сессия 8: Финальные фиксы превью

Цель: устранить остаточные проблемы превью (HMR-конфликты, отсутствие авто-перезагрузки iframe), не допускать деплой неработающей сборки, провести итоговый аудит и зафиксировать env.

Коммиты: 22, 23, 24.

### Коммит 22: Отключить HMR + перезагрузка iframe

**Файлы**
- Изменить: `src/studio/agents/coder.py`
- Изменить: `frontend/components/studio/PreviewPanel.tsx`

**Что делать**

1. В `SYSTEM_EN` CoderAgent добавить правило про конфиг dev-сервера (HMR off для Vite, корректный dev-скрипт для Next.js).
2. В `PreviewPanel` перезагружать iframe (через смену `key`) по SSE-событию завершения шага.

**Код**

Дополнить `SYSTEM_EN` в `src/studio/agents/coder.py` блоком:

```
For Vite/React/Vue projects, always include in vite.config.ts:
server: { host: true, port: 3000, hmr: false }
For Next.js projects: ALWAYS set package.json scripts.dev to "next dev -p 3000 -H 0.0.0.0".
```

В `frontend/components/studio/PreviewPanel.tsx`:

```tsx
const [iframeKey, setIframeKey] = useState(0);

// В обработчике SSE (EventSource):
if (event.type === "step_completed" || event.type === "coder_done") {
  setIframeKey(k => k + 1);
}

// В JSX:
<iframe key={iframeKey} src={previewUrl} className="w-full h-full border-0" />
```

**Проверка**: после завершения шага превью автоматически перезагружается; HMR-ошибки в логах dev-сервера отсутствуют.

### Коммит 23: Build-gate перед деплоем

**Файлы**
- Изменить: `src/studio/sandbox.py`
- Изменить: `src/studio/tasks.py`

**Что делать**

1. Расширить `run_build_check` для Next.js (полный `pnpm build`) и прочих стеков (`tsc --noEmit` с fallback на build).
2. В `deploy_to_vercel` перед деплоем выполнить build-проверку; при ненулевом exit — опубликовать `deploy_failed` и прервать деплой.

**Код**

В `src/studio/sandbox.py`:

```python
def run_build_check(container_id: str, is_nextjs: bool = False) -> tuple:
    if is_nextjs:
        return exec_command(container_id, 'pnpm build 2>&1 | tail -n 150')
    return exec_command(
        container_id,
        'pnpm -s exec tsc --noEmit 2>&1 | tail -n 100 || pnpm -s build 2>&1 | tail -n 120',
    )
```

В `src/studio/tasks.py`, в `deploy_to_vercel` перед самим деплоем:

```python
project = StudioProject.objects.get(id=project_id)
is_next = project.target_stack == 'nextjs'
if project.sandbox_container_id:
    exit_code, output = sandbox.run_build_check(project.sandbox_container_id, is_nextjs=is_next)
    if exit_code != 0:
        publish_event(project_id, 'deploy_failed', {
            'reason': 'Сборка не прошла перед деплоем. Исправьте ошибки.',
            'details': output[-500:],
        })
        return
```

Примечание: поле стека проекта — `target_stack`. Значение для Next.js — `'nextjs'` (согласовать со значениями `StackCards`).

**Проверка**: проект с ошибкой сборки не деплоится, приходит событие `deploy_failed` с деталями; корректный проект деплоится.

### Коммит 24: Итоговый аудит + .env.example

**Файлы**
- Изменить: `.env.example`
- Аудит: `src/studio/tasks.py`, `src/config/celery.py`, миграции

**Что делать**

1. Добавить новые переменные в `.env.example`.
2. Проверить все импорты в `tasks.py` (`hashlib`, `timezone`, `ESCALATION_MAP`, `release_reserve`, `kill_sandbox`).
3. Убедиться, что `studio.watchdog_pipelines` зарегистрирован в beat.
4. Проверить, что миграции созданы и применяются без конфликтов; `coder_model` полностью удалён, `ai_model` и поля анти-цикла на месте.

**Код**

Добавить в `.env.example`:

```
STUDIO_PROMPT_LANG=en
STUDIO_STEP_STALL_SEC=240
STUDIO_PIPELINE_MAX_SEC=2700
STUDIO_MAX_ITERATIONS=5
STUDIO_TOKEN_ENCRYPTION_KEY=  # Fernet key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Аудит-команды:

```bash
cd src
python manage.py makemigrations studio --check --dry-run   # не должно быть незакоммиченных изменений моделей
python manage.py migrate                                   # все миграции применяются
python -c "import ast,sys; ast.parse(open('studio/tasks.py').read())"  # синтаксис
```

**Проверка**: пайплайн проходит полный цикл на тестовом проекте каждого стека (HTML/React/Vue/Next.js), превью открывается, деплой блокируется при ошибке сборки, watchdog корректно завершает зависшие пайплайны.

---

## Чеклист финальной проверки

Backend:
- [ ] `src/studio/models_catalog.py` создан, 15 моделей, `MODEL_TIER`, `ESCALATION_MAP`.
- [ ] `StudioProject.ai_model` существует; `coder_model` удалён data-миграцией.
- [ ] `StudioPipelineState`: `last_files_hash`, `same_diff_count`, `last_error_signature`, `error_repeat_count`, `started_at`.
- [ ] `billing.STAR_RATE` содержит `coder: 1.7`; `coder_tier_for_model` и `estimate_stars` используют `MODEL_TIER`.
- [ ] `BaseAgent.resolve_model()`; хардкод `MODEL_FAST/SMART` удалён.
- [ ] `CoderAgent._pick_model()` эскалирует на `[COMPLEX]`.
- [ ] `STUDIO_PROMPT_LANG` и `pick_prompt`; все 7 агентов имеют `SYSTEM_RU`/`SYSTEM_EN`.
- [ ] Детектор одинакового diff (`paused_on_loop`) и повторной ошибки (эскалация) в `tasks.py`.
- [ ] `watchdog_pipelines` зарегистрирован в beat (каждые 120 с); `started_at` ставится в `run_pipeline`.
- [ ] `PipelineSkipView` + роут `pipeline/skip/`; сериализатор отдаёт `max_iterations`.
- [ ] `sandbox.sync_all`; `start_dev_server` различает Next.js/Vite; `wait_for_ready` с warmup и timeout 150.
- [ ] `<base href>` инжектится в fallback HTML `PreviewProxyView`.
- [ ] SSE `progress` вокруг `install_deps`.
- [ ] `ModelsCatalogView` + роут `models/`.
- [ ] Сериализатор принимает `selected_features`; сохраняются в `interview_data`.
- [ ] Analyst/Planner учитывают features.
- [ ] `run_build_check` расширён; build-gate в `deploy_to_vercel`.
- [ ] `.env.example` обновлён; миграции чисты (`makemigrations --check` без изменений).

Frontend:
- [ ] `PipelineTimeline.tsx` подключён в `StudioLayout`.
- [ ] `PipelineRecovery.tsx`; `skipStep`/`resumePipeline` в `studio.ts`.
- [ ] UI выбора модели с `<optgroup>` и оценкой звёзд; `getModels`/`StudioModel`.
- [ ] `StudioHero.tsx` показывается при пустом списке проектов.
- [ ] `StackCards.tsx` заменил `<select>` стека.
- [ ] Карточки режимов вместо кнопок.
- [ ] `features.ts` + `FeatureSelector.tsx` в форме «С нуля»; `selected_features` в payload.
- [ ] `PreviewPanel` перезагружает iframe по SSE завершения шага.

Дизайн-система:
- [ ] Только иконки Lucide React, без эмодзи.
- [ ] Все цвета через CSS-переменные.
- [ ] `python scripts/check_no_emoji.py` проходит.

Сквозная проверка:
- [ ] Полный цикл пайплайна на проекте каждого стека (HTML/React/Vue/Next.js).
- [ ] Превью открывается и авто-перезагружается.
- [ ] Деплой блокируется при ошибке сборки.
- [ ] Watchdog завершает зависший пайплайн и возвращает резерв звёзд.
