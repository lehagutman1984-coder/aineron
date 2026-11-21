"""
Добавляет 10 новых текстовых моделей, вышедших в сентябре-ноябре 2026 и
найденных у провайдеров, но отсутствовавших в каталоге (по запросу
пользователя, 2026-11-21):

  Claude Haiku 5.5, Claude Fable 5.2, GPT-6.2 Sol, GPT-6.2 Astra,
  GPT-6.1 Terra, Gemini 4 Hydrogen, Gemini 4 Neon, Gemini 3.8 Flash,
  GLM 5.3, DeepSeek V4.1 Flash.

КАК ОТОБРАНЫ (не по названию на скриншоте, а по проверке живьём):
- Сверка живых каталогов apimart (GET /v1/models, основной провайдер текста),
  laozhang и публичного каталога CometAPI (резерв) с живой БД на .ru, а не с
  файлами команд. Дата выхода — только по CometAPI (`created`/`published_at`):
  у apimart и laozhang поле `created` — заглушка (2021-07-20 / 2023-03-01).
- Критерий «есть резерв»: ОДНА И ТА ЖЕ строка модели у apimart и CometAPI
  (FallbackClient — passthrough, см. providers.py). Единственное расхождение —
  Fable 5.2 (apimart `claude-fable-5.2`, CometAPI `claude-fable-5-2`): закрыто
  записью в providers.TEXT_COMETAPI_MODEL_OVERRIDES.
- Каждая модель проверена реальным chat.completions (потоковым) на обоих
  провайдерах с проверкой поля `model` в ответе, а не только кода 200.
  Зрение (handle_photo=True) подтверждено реальной картинкой для 9 из 10:
  ответ «Red» на красный квадрат. GLM 5.3 принимает только text (apimart
  400 «type must be text») — handle_photo=False.
- Не взяты Gemini 4 Argon/Carbon/Krypton (помечены upcoming у CometAPI,
  Carbon отвечал пусто на коротком лимите), MiniMax M3 (вышла в июне, старше
  остальных), модели-заглушки CometAPI с ценой 75/75 (placeholder).

ЦЕНА (cost_kopecks) — по правилу из align_text_pricing_to_competitors.py:
  RouterAI (routerai.ru, JSON-LD страницы модели, снято 2026-11-21) за
  «типичное сообщение» (профиль 6000 вход + 1500 выход) × 0.95, но не ниже
  оптовой с маржой (опт CometAPI × ratio 0.8 — это цена РЕЗЕРВА, т.е.
  консервативная верхняя граница опта; ₽/$ ≈ 91, маржа 1.05).
  модель             RouterAI вх/вых ₽/1М   конкурент×0.95   пол (опт)   итог
  gpt-6.2-sol           214 / 1068            2.74₽           2.06₽      274 коп.
  gpt-6.2-astra         855 / 4274           10.96₽           8.26₽     1096 коп.
  gpt-6.1-terra         107 / 534             1.37₽           ~1.0₽      137 коп.
  claude-fable-5.2      855 / 4274           10.96₽           8.26₽     1096 коп.
  claude-haiku-5.5      10.7 / 53             0.14₽            н/д       14 коп.
  gemini-4-hydrogen     160 / 801             2.05₽           1.55₽      205 коп.
  gemini-4-neon         321 / 1603            4.11₽           3.10₽      411 коп.
  gemini-3.8-flash       80 / 401             1.03₽           0.77₽      103 коп.
  glm-5.3                 7 / 149             0.25₽           1.15₽      115 коп. (ПОЛ)
  deepseek-v4.1-flash   5.85 / 23             0.07₽            н/д        10 коп. (MIN_CHARGE)
GLM 5.3: у RouterAI в разы дешевле опта CometAPI (у них прямой Z.ai) — взят
пол, т.к. реальный опт apimart по этой модели неизвестен. Если apimart
дешевле — цену можно снижать. Haiku 5.5 и DeepSeek V4.1 Flash: оптовых цен у
CometAPI нет, ориентир — только конкурент (K≈105 эквивалент по прошлым раундам).

Описания: description_ru И description_en заданы ЯВНО (а не bare description=,
который modeltranslation роутит по активному языку инстанса — так на .net
в description_en попадал русский текст, см. c09ed68).

Запуск: docker compose exec web python manage.py add_new_models_2026_11_21
        docker compose exec web python manage.py add_new_models_2026_11_21 --dry-run
Идемпотентна: существующий slug пропускается, чужие модели не трогаются
(НИКОГДА не запускать add_laozhang_models целиком ради этого — update_or_create
сбросит вручную подобранные цены, см. docstring add_new_models.py, BUG-F).
"""
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from aitext.models import Category, NeuralNetwork


MODELS = [
    {
        'name': 'Claude Haiku 5.5', 'slug': 'claude-haiku-5-5', 'model_name': 'claude-haiku-5-5',
        'order': 87, 'cost_kopecks': 14, 'handle_photo': True, 'avatar_from': 'claude-haiku-4-5',
        'description_ru': 'Самая быстрая и доступная модель линейки Claude 5.5 от Anthropic — для массовых задач и быстрых ответов.',
        'description_en': 'The fastest and most affordable model in the Claude 5.5 line from Anthropic — built for high-volume tasks and quick replies.',
    },
    {
        'name': 'Claude Fable 5.2', 'slug': 'claude-fable-5-2', 'model_name': 'claude-fable-5.2',
        'order': 88, 'cost_kopecks': 1096, 'handle_photo': True, 'avatar_from': 'claude-fable-5-1',
        'description_ru': 'Следующая версия Claude Fable — модель для длинных автономных задач и сложных рассуждений.',
        'description_en': 'The next Claude Fable release — a model for long autonomous tasks and complex reasoning.',
    },
    {
        'name': 'GPT-6.2 Sol', 'slug': 'gpt-6-2-sol', 'model_name': 'gpt-6.2-sol',
        'order': 89, 'cost_kopecks': 274, 'handle_photo': True, 'avatar_from': 'gpt-6-1-sol',
        'description_ru': 'Новая версия GPT-6 Sol от OpenAI — универсальная модель для текста, кода и анализа изображений.',
        'description_en': 'The new GPT-6 Sol release from OpenAI — a versatile model for text, code and image understanding.',
    },
    {
        'name': 'GPT-6.2 Astra', 'slug': 'gpt-6-2-astra', 'model_name': 'gpt-6.2-astra',
        'order': 90, 'cost_kopecks': 1096, 'handle_photo': True, 'avatar_from': 'gpt-6-astra',
        'description_ru': 'Флагманская ветка GPT-6.2 от OpenAI — максимальное качество на сложных задачах и рассуждениях.',
        'description_en': 'The flagship branch of OpenAI GPT-6.2 — top quality on hard tasks and reasoning.',
    },
    {
        'name': 'GPT-6.1 Terra', 'slug': 'gpt-6-1-terra', 'model_name': 'gpt-6.1-terra',
        'order': 91, 'cost_kopecks': 137, 'handle_photo': True, 'avatar_from': 'gpt-6-sol',
        'description_ru': 'Сбалансированная модель семейства GPT-6.1 от OpenAI — хорошее качество по умеренной цене.',
        'description_en': 'A balanced model in the OpenAI GPT-6.1 family — strong quality at a moderate price.',
    },
    {
        'name': 'Gemini 4 Hydrogen', 'slug': 'gemini-4-hydrogen', 'model_name': 'gemini-4-hydrogen',
        'order': 92, 'cost_kopecks': 205, 'handle_photo': True, 'avatar_from': 'gemini-3-7-flash',
        'description_ru': 'Модель поколения Gemini 4 от Google: мультимодальная, контекст до 1M токенов, быстрые ответы.',
        'description_en': 'A Google Gemini 4 generation model: multimodal, up to 1M tokens of context, fast responses.',
    },
    {
        'name': 'Gemini 4 Neon', 'slug': 'gemini-4-neon', 'model_name': 'gemini-4-neon',
        'order': 93, 'cost_kopecks': 411, 'handle_photo': True, 'avatar_from': 'gemini-3-7-flash',
        'description_ru': 'Модель поколения Gemini 4 от Google в более высоком классе: мультимодальная, контекст до 1M токенов.',
        'description_en': 'A higher-tier Google Gemini 4 generation model: multimodal, up to 1M tokens of context.',
    },
    {
        'name': 'Gemini 3.8 Flash', 'slug': 'gemini-3-8-flash', 'model_name': 'gemini-3.8-flash',
        'order': 94, 'cost_kopecks': 103, 'handle_photo': True, 'avatar_from': 'gemini-3-7-flash',
        'description_ru': 'Быстрая и недорогая модель Google Gemini 3.8 — мультимодальная, контекст до 1M токенов.',
        'description_en': 'A fast, low-cost Google Gemini 3.8 model — multimodal, up to 1M tokens of context.',
    },
    {
        'name': 'GLM 5.3', 'slug': 'glm-5-3', 'model_name': 'glm-5.3',
        'order': 95, 'cost_kopecks': 115, 'handle_photo': False, 'avatar_file': 'neural_avatars/zai.png',
        'description_ru': 'Новая версия флагманской модели Zhipu AI (Z.ai) — сильна в коде, агентных задачах и рассуждениях.',
        'description_en': 'The new flagship model from Zhipu AI (Z.ai) — strong at coding, agentic tasks and reasoning.',
    },
    {
        'name': 'DeepSeek V4.1 Flash', 'slug': 'deepseek-v4-1-flash', 'model_name': 'deepseek-v4.1-flash',
        'order': 96, 'cost_kopecks': 10, 'handle_photo': True, 'avatar_from': 'deepseek-v4-flash',
        'description_ru': 'Быстрая и очень доступная модель DeepSeek V4.1 — для массовых запросов, кода и работы с изображениями.',
        'description_en': 'A fast, very affordable DeepSeek V4.1 model — for high-volume requests, coding and image input.',
    },
]


class Command(BaseCommand):
    help = 'Добавляет 10 новых текстовых моделей (get_or_create по slug, не трогает остальные)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только показать, что будет сделано')

    def _attach_avatar(self, network, spec):
        """Копирует аватар соседней модели того же вендора (без сети, работает
        на обоих инстансах). Если источника нет — остаётся ui-avatars fallback."""
        src = None
        if spec.get('avatar_from'):
            sib = NeuralNetwork.objects.filter(slug=spec['avatar_from']).first()
            if sib and sib.avatar:
                src = sib.avatar
        elif spec.get('avatar_file'):
            from django.core.files.storage import default_storage
            if default_storage.exists(spec['avatar_file']):
                src = default_storage.open(spec['avatar_file'])
        if not src:
            self.stdout.write(self.style.WARNING(f"  [WARN] {spec['slug']}: аватар-источник не найден, будет fallback"))
            return
        try:
            data = src.read()
            network.avatar.save(f"{spec['slug']}.png", ContentFile(data), save=True)
        except Exception as e:  # аватар не критичен — не валим добавление модели
            self.stdout.write(self.style.WARNING(f"  [WARN] {spec['slug']}: не удалось скопировать аватар: {e}"))

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        # Категория по name_ru — единственное поле, одинаковое на .ru и .net
        # (см. a40f7e8: get_or_create(name=...) и поиск по slug падали на .net).
        category = Category.objects.filter(name_ru='Текст').first() \
            or Category.objects.get_or_create(name='Текст')[0]

        created = 0
        for spec in MODELS:
            existing = NeuralNetwork.objects.filter(slug=spec['slug']).first()
            by_model = NeuralNetwork.objects.filter(model_name=spec['model_name']).first()
            if existing or by_model:
                found = existing or by_model
                self.stdout.write(self.style.WARNING(f"{spec['slug']}: уже существует (slug={found.slug}, id={found.id}), пропуск"))
                continue

            self.stdout.write(
                f"{spec['slug']}: создать \"{spec['name']}\" model_name={spec['model_name']} "
                f"cost_kopecks={spec['cost_kopecks']} ({spec['cost_kopecks']/100:.2f}₽) photo={spec['handle_photo']}"
            )
            if dry_run:
                continue

            network = NeuralNetwork.objects.create(
                name=spec['name'],
                slug=spec['slug'],
                category=category,
                # Оба поля явно: bare description= роутится по активному языку
                # инстанса и на .net клал бы русский текст в description_en.
                description_ru=spec['description_ru'],
                description_en=spec['description_en'],
                model_name=spec['model_name'],
                provider='openrouter',
                order=spec['order'],
                cost_per_message=max(spec['cost_kopecks'] // 100, 1),
                cost_kopecks=spec['cost_kopecks'],
                is_active=True,
                is_new=True,
                handle_photo=spec['handle_photo'],
                handle_text_files=True,
                translate_to_english=False,
                config_json={},
            )
            self._attach_avatar(network, spec)
            created += 1

        if dry_run:
            self.stdout.write(self.style.WARNING('\n--dry-run: изменения НЕ сохранены'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nГотово: создано {created}'))
