"""Каталог моделей Studio: единый источник правды для UI, биллинга и эскалации."""

STUDIO_MODELS = [
    {'id': 'claude-sonnet-4-6',          'label': 'Claude Sonnet 4.6',  'category': 'smart',     'tier': 'smart',  'description': 'Лучший баланс качества и скорости'},
    {'id': 'claude-opus-4-8',            'label': 'Claude Opus 4.8',    'category': 'smart',     'tier': 'smart',  'description': 'Максимальное качество, сложная архитектура'},
    {'id': 'claude-haiku-4-5-20251001',  'label': 'Claude Haiku 4.5',   'category': 'fast',      'tier': 'fast',   'description': 'Быстрый Claude для простых задач'},
    {'id': 'gpt-5',                      'label': 'GPT-5',              'category': 'smart',     'tier': 'smart',  'description': 'Топовый GPT, сильная логика и рефакторинг'},
    {'id': 'gpt-5-mini',                 'label': 'GPT-5 Mini',         'category': 'fast',      'tier': 'fast',   'description': 'Дешёвый GPT-5 для рутинных шагов'},
    {'id': 'gpt-4.1',                    'label': 'GPT-4.1',            'category': 'smart',     'tier': 'smart',  'description': 'Надёжный генералист по коду'},
    {'id': 'gpt-4.1-mini',               'label': 'GPT-4.1 Mini',       'category': 'fast',      'tier': 'fast',   'description': 'Быстрый и дешёвый генералист'},
    {'id': 'gpt-4o',                     'label': 'GPT-4o',             'category': 'fast',      'tier': 'fast',   'description': 'Быстрый мультимодальный'},
    {'id': 'deepseek-v3.2',              'label': 'DeepSeek V3.2',      'category': 'fast',      'tier': 'fast',   'description': 'Сильный код за низкую цену'},
    {'id': 'deepseek-v4-pro',            'label': 'DeepSeek V4 Pro',    'category': 'smart',     'tier': 'smart',  'description': 'Старшая DeepSeek, качество ближе к топу'},
    {'id': 'deepseek-r1',                'label': 'DeepSeek R1',        'category': 'reasoning', 'tier': 'smart',  'description': 'Пошаговые рассуждения, сложная логика'},
    {'id': 'qwen3-coder-plus',           'label': 'Qwen3 Coder Plus',   'category': 'coder',     'tier': 'coder',  'description': 'Специализирован на коде'},
    {'id': 'qwen3-235b-a22b',            'label': 'Qwen3 235B',         'category': 'smart',     'tier': 'smart',  'description': 'Крупная Qwen, сильный генералист'},
    {'id': 'kimi-k2',                    'label': 'Kimi K2',            'category': 'coder',     'tier': 'coder',  'description': 'Длинный контекст, сильна в коде'},
    {'id': 'gemini-2.5-pro',             'label': 'Gemini 2.5 Pro',     'category': 'smart',     'tier': 'smart',  'description': 'Длинный контекст, крупные проекты'},
]

DEFAULT_STUDIO_MODEL = 'qwen3-coder-plus'

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

# Default per-agent models: per-agent sensible defaults before project.ai_model
DEFAULT_AGENT_MODELS = {
    'interviewer': 'deepseek-v3.2',       # fast: simple JSON questions
    'architect':   'claude-opus-4-8',     # smart: design quality matters most
    'coder':       'qwen3-coder-plus',    # coder: specialized for code generation
    'guardian':    'claude-sonnet-4-6',   # smart: reliable review without over-nitpicking
}


def is_valid_model(model_id: str) -> bool:
    return model_id in MODEL_TIER
