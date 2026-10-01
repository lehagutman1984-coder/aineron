"""
Добавляет GPT Image 2.5 Sunburst и GPT Image 2.5 Flare в каталог — по прямому
запросу пользователя, 2026-10-01 (три скриншота: каталог CometAPI, прайс-лист
laozhang.ai x2).

Проверено по обоим провайдерам: model_name идентичен на laozhang и CometAPI —
"gpt-image-2.5-sunburst" / "gpt-image-2.5-flare" (не путать с datированными
строками прайс-листа laozhang "...−2026-09-08" — это просто зафиксированный
на дату снимок цены для прозрачности биллинга, а не отдельное значение
параметра model= для вызова API; подтверждено тем, что CometAPI отдаёт те же
голые id без даты).

Цена (опт×1.05, тот же принцип, что в apply_image_price_margin_floor.py):
laozhang даёт ОБЕИМ 2.5-моделям (датированные строки прайс-листа) ТОЧНО ТЕ ЖЕ
токенные тарифы, что уже были у gpt-image-2 при расчёте его цены (align_
image_pricing_to_competitors.py) — input $5/1M, completion $30/1M, cache
$1.25/1M. Раз опт по токенам идентичен gpt-image-2, оставляем ЕГО ЖЕ
cost_kopecks=238 (2.38₽) для обеих новых моделей — не пересчитываем через
headline-цену CometAPI "$4/1M tokens" с грид-страницы каталога: она не
разбита на input/completion/cache (в отличие от детального прайс-листа
laozhang) и могла бы описывать другую метрику — рисковать занижением цены
по непрозрачной цифре не стали, когда есть прямое совпадение по уже
проверенной методике.

"Dynamic pricing" в таблице laozhang для недатированных gpt-image-2.5-sunburst/
flare — то же самое обозначение, что уже стоит у действующего gpt-image-2
(тоже "Dynamic pricing" на laozhang) — это не особый риск именно для 2.5,
а стандартное для всей линейки обозначение "цена считается по факту
использования токенов", не "цена непредсказуема при каждом вызове".

Аватар не проставлен (нет готового файла) — доставить через
`download_avatars` или вручную через админку.

Запуск: docker-compose exec web python manage.py add_gpt_image_25_models
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork, Category


MODELS = [
    {
        'name': 'GPT Image 2.5 Sunburst',
        'slug': 'gpt-image-2-5-sunburst',
        'model_name': 'gpt-image-2.5-sunburst',
        'order': 48,
        'description': 'Обновлённая модель OpenAI для генерации изображений — улучшенная детализация и свет.',
    },
    {
        'name': 'GPT Image 2.5 Flare',
        'slug': 'gpt-image-2-5-flare',
        'model_name': 'gpt-image-2.5-flare',
        'order': 49,
        'description': 'Обновлённая модель OpenAI для генерации изображений — альтернативный рендер 2.5-поколения.',
    },
]

COST_KOPECKS = 238  # = gpt-image-2 (см. docstring — идентичный опт по токенам)
COST_PER_MESSAGE = COST_KOPECKS // 100

CONFIG_JSON_TEMPLATE = {
    'metadata': {
        'output_type': 'image',
        'requires_input_images': False,
        # заполняется per-модель ниже
        'cometapi_fallback_model': None,
    },
    'constraints': {},
    'ui_settings': {
        'sections': [
            {
                'title': 'Настройки изображения',
                'fields': [
                    {
                        'name': 'size',
                        'type': 'select',
                        'label': 'Размер',
                        'options': [
                            {'label': '1024×1024 (квадрат)', 'value': '1024x1024', 'extra_cost': 0},
                            {'label': '1024×1536 (вертикаль)', 'value': '1024x1536', 'extra_cost': 0},
                            {'label': '1536×1024 (горизонталь)', 'value': '1536x1024', 'extra_cost': 0},
                        ],
                        'extra_cost': 0,
                    },
                    {
                        'name': 'quality',
                        'type': 'select',
                        'label': 'Качество',
                        'options': [
                            {'label': 'Авто', 'value': 'auto', 'extra_cost': 0},
                            {'label': 'Низкое', 'value': 'low', 'extra_cost': 0},
                            {'label': 'Среднее', 'value': 'medium', 'extra_cost': 0},
                            {'label': 'Высокое', 'value': 'high', 'extra_cost': 10},
                        ],
                        'extra_cost': 0,
                    },
                ],
            }
        ]
    },
    'api_defaults': {'n': 1, 'size': '1024x1024', 'quality': 'auto'},
}


class Command(BaseCommand):
    help = 'Добавляет GPT Image 2.5 Sunburst/Flare в каталог (get_or_create, не трогает остальные модели)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только показать, что будет сделано')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        category, _ = Category.objects.get_or_create(name='Изображения')

        for spec in MODELS:
            import copy
            config_json = copy.deepcopy(CONFIG_JSON_TEMPLATE)
            config_json['name'] = spec['name']
            config_json['metadata']['cometapi_fallback_model'] = spec['model_name']

            existing = NeuralNetwork.objects.filter(slug=spec['slug']).first()
            if existing:
                self.stdout.write(self.style.WARNING(f"{spec['slug']}: уже существует (id={existing.id}), пропуск"))
                continue

            self.stdout.write(
                f"{spec['slug']}: создать \"{spec['name']}\" model_name={spec['model_name']} "
                f"cost_kopecks={COST_KOPECKS} ({COST_KOPECKS/100:.2f}₽)"
            )
            if dry_run:
                continue

            NeuralNetwork.objects.create(
                name=spec['name'],
                slug=spec['slug'],
                category=category,
                description=spec['description'],
                description_ru=spec['description'],
                model_name=spec['model_name'],
                provider='fal-ai',
                order=spec['order'],
                cost_per_message=COST_PER_MESSAGE,
                cost_kopecks=COST_KOPECKS,
                is_active=True,
                handle_photo=False,
                translate_to_english=False,
                config_json=config_json,
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('\n--dry-run: изменения НЕ сохранены'))
        else:
            self.stdout.write(self.style.SUCCESS('\nГотово'))
