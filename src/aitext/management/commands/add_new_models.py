"""
Добавляет новые текстовые модели laozhang.ai: Gemini 3.1 Pro, GLM 5, GPT-5 Mini/Pro,
Qwen 3.5 Flash/Plus, MiniMax M2.7.
Запуск: docker-compose exec web python manage.py add_new_models

BUG-F (TELEGRAM_SUPREMACY_PLAN_V2.md): раньше здесь же лежали ещё 17 моделей
(Seedream, Gemini Image, GPT Image 1.5, DeepSeek V3.2/V4, Grok 4.3, Kimi,
GLM 4.6, MiniMax M2.5), продублированные в add_laozhang_models.py с другими
cost_per_message/cost_kopecks — обе команды используют update_or_create,
поэтому цена в проде зависела от того, какая команда запускалась последней
(была именно add_laozhang_models.py — цены на её стороне сверены с БД и
оставлены как источник истины). Дубликаты удалены отсюда, чтобы повторный
запуск этой команды больше не мог тихо изменить цены моделей, за которые
она не отвечает.
"""
from django.core.management.base import BaseCommand
from aitext.models import Category, NeuralNetwork


NEW_TEXT_MODELS = [
    # Gemini новые версии
    dict(name='Gemini 3.1 Pro', slug='gemini-3-1-pro', model_name='gemini-3.1-pro-preview', cost_per_message=25, order=34,
         description='Флагманский Gemini 3.1 Pro с глубоким мультимодальным пониманием.',
         handle_photo=True),

    # GLM новые версии
    dict(name='GLM 5', slug='glm-5', model_name='glm-5', cost_per_message=10, order=72,
         description='Новейший флагман Zhipu AI пятого поколения.'),

    # GPT-5 расширение
    dict(name='GPT-5 Mini', slug='gpt-5-mini', model_name='gpt-5-mini', cost_per_message=15, order=7,
         description='Компактный GPT-5 — умный и быстрый для повседневных задач.',
         handle_photo=True, is_popular=True),
    dict(name='GPT-5 Pro', slug='gpt-5-pro', model_name='gpt-5-pro', cost_per_message=60, order=8,
         description='Самый мощный GPT-5 Pro для сложнейших профессиональных задач.',
         handle_photo=True),

    # Qwen 3.5
    dict(name='Qwen 3.5 Flash', slug='qwen3-5-flash', model_name='qwen3.5-flash', cost_per_message=3, order=53,
         description='Сверхбыстрый и дешёвый Qwen 3.5 Flash.'),
    dict(name='Qwen 3.5 Plus', slug='qwen3-5-plus', model_name='qwen3.5-plus', cost_per_message=8, order=54,
         description='Улучшенный Qwen 3.5 Plus с расширенными возможностями.'),

    # MiniMax
    dict(name='MiniMax M2.7', slug='minimax-m2-7', model_name='MiniMax-M2.7', cost_per_message=15, order=76,
         description='Мощная модель MiniMax M2.7 с поддержкой длинного контекста.'),
]


class Command(BaseCommand):
    help = 'Добавляет новые текстовые модели: Gemini 3.1 Pro, GLM 5, GPT-5 Mini/Pro, Qwen 3.5, MiniMax M2.7'

    def _get_or_create_category(self, name, slug, icon, order):
        # slug-первый lookup (не только name): под modeltranslation (INTL_MODE=1,
        # aineron.net) name фильтруется по переведённому полю name_en, которое
        # может не совпадать с переданным ru-текстом — тот же класс бага, что
        # чинили в add_laozhang_models.py (см. его _get_or_create_category).
        cat = Category.objects.filter(slug=slug).first() or Category.objects.filter(name=name).first()
        if cat:
            return cat
        base_slug = slug
        i = 1
        while Category.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{i}"
            i += 1
        return Category.objects.create(name=name, slug=slug, icon=icon, order=order)

    def handle(self, *args, **options):
        text_cat = self._get_or_create_category('Текст', 'text', 'fas fa-comment-dots', 1)

        self.stdout.write('\n=== Новые текстовые модели ===')
        for m in NEW_TEXT_MODELS:
            network, created = NeuralNetwork.objects.update_or_create(
                slug=m['slug'],
                defaults={
                    'name': m['name'],
                    'category': text_cat,
                    'model_name': m['model_name'],
                    'cost_per_message': m['cost_per_message'],
                    'order': m.get('order', 99),
                    'description': m.get('description', ''),
                    'provider': 'openrouter',
                    'is_active': True,
                    'handle_photo': m.get('handle_photo', False),
                    'handle_text_files': True,
                    'is_popular': m.get('is_popular', False),
                }
            )
            status = 'создана' if created else 'обновлена'
            self.stdout.write(f'  {status}: {network.name} ({network.model_name})')

        self.stdout.write(f'\nГотово! Обработано: {len(NEW_TEXT_MODELS)} моделей')
        self.stdout.write('\nДалее:')
        self.stdout.write('  1. Проверьте модели в Django Admin')
        self.stdout.write('  2. Загрузите аватары: python manage.py download_avatars')
