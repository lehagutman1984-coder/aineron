from django.core.management.base import BaseCommand
from studio.models import StudioTemplate

RU_TEMPLATES = [
    {
        'slug': 'ru-ecommerce',
        'name': 'Интернет-магазин (Россия)',
        'description': 'Магазин с оплатой через Робокассу и авторизацией VK ID',
        'stack': 'nextjs',
        'is_public': True,
        'features': ['robokassa', 'vk_id'],
        'seed_prompt': (
            'Создай интернет-магазин на Next.js для российского рынка: каталог товаров с карточками, '
            'корзина с подсчётом суммы, оформление заказа с оплатой через Робокассу, '
            'авторизация через VK ID. Стиль современного e-commerce, тёмная тема.'
        ),
        'order': 10,
    },
    {
        'slug': 'ru-realty',
        'name': 'Сервис недвижимости',
        'description': 'Каталог объектов с Яндекс.Картами и формой заявки',
        'stack': 'nextjs',
        'is_public': True,
        'features': ['yandex_maps'],
        'seed_prompt': (
            'Создай сайт агентства недвижимости на Next.js: каталог объектов с фильтрами '
            '(цена, район, тип), карточки объектов с фото, Яндекс.Карта с метками, '
            'форма заявки на показ. Профессиональный дизайн.'
        ),
        'order': 11,
    },
    {
        'slug': 'ru-telegram-bot-landing',
        'name': 'Лендинг Telegram-бота',
        'description': 'Промо-страница бота с кнопкой Telegram Login',
        'stack': 'nextjs',
        'is_public': True,
        'features': ['telegram_login'],
        'seed_prompt': (
            'Создай лендинг для Telegram-бота на Next.js: hero с названием и описанием бота, '
            'секция возможностей (3-4 карточки), виджет Telegram Login для регистрации, '
            'FAQ и footer. Используй цвета и стиль Telegram.'
        ),
        'order': 12,
    },
    {
        'slug': 'ru-b2b-saas',
        'name': 'B2B SaaS (Россия)',
        'description': 'Корпоративный SaaS с оплатой через Робокассу и VK ID',
        'stack': 'nextjs',
        'is_public': True,
        'features': ['robokassa', 'vk_id'],
        'seed_prompt': (
            'Создай B2B SaaS-приложение для российского рынка на Next.js: дашборд с метриками, '
            'управление аккаунтом, тарифные планы с оплатой через Робокассу, '
            'авторизация через VK ID или email. Минималистичный корпоративный дизайн.'
        ),
        'order': 13,
    },
]

TEMPLATES = [
    {
        'slug': 'landing',
        'name': 'Landing Page',
        'description': 'Продающий лендинг с hero-секцией, features, pricing и CTA',
        'stack': 'nextjs',
        'is_public': True,
        'seed_prompt': (
            'Создай продающий лендинг на Next.js: hero с заголовком и подзаголовком, '
            'секция преимуществ (3-4 карточки с иконками), pricing с тремя тарифами, '
            'форма обратной связи и footer. Стиль минималистичный, тёмная/светлая тема.'
        ),
        'order': 1,
    },
    {
        'slug': 'crud-app',
        'name': 'CRUD App',
        'description': 'Полноценное приложение с таблицами, формами и CRUD-операциями',
        'stack': 'nextjs',
        'is_public': True,
        'seed_prompt': (
            'Создай веб-приложение с CRUD-интерфейсом: список записей в таблице с пагинацией, '
            'модальная форма создания/редактирования, подтверждение удаления, '
            'поиск и фильтрация. API на Next.js API Routes с localStorage.'
        ),
        'order': 2,
    },
    {
        'slug': 'chat-bot',
        'name': 'Chat Interface',
        'description': 'Интерфейс чата с историей сообщений и потоковым ответом',
        'stack': 'nextjs',
        'is_public': True,
        'seed_prompt': (
            'Создай интерфейс чат-бота на Next.js: боковая панель с историей чатов, '
            'основная область сообщений с markdown-рендерингом, поле ввода с кнопкой отправки, '
            'индикатор набора текста. Стиль современного AI-чата.'
        ),
        'order': 3,
    },
    {
        'slug': 'portfolio',
        'name': 'Portfolio',
        'description': 'Персональное портфолио разработчика с проектами и контактами',
        'stack': 'nextjs',
        'is_public': True,
        'seed_prompt': (
            'Создай персональный сайт-портфолио: hero с аватаром и кратким описанием, '
            'секция навыков с прогресс-барами, галерея проектов в виде карточек с тегами, '
            'таймлайн опыта работы и форма контакта. Dark-first дизайн.'
        ),
        'order': 4,
    },
]


class Command(BaseCommand):
    help = 'Seed default project templates (idempotent)'

    def handle(self, *args, **options):
        all_templates = TEMPLATES + RU_TEMPLATES
        for data in all_templates:
            obj, created = StudioTemplate.objects.update_or_create(
                slug=data['slug'],
                defaults={k: v for k, v in data.items() if k != 'slug'},
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'{action}: {obj.name}')
        self.stdout.write(self.style.SUCCESS(f'Done: {len(all_templates)} templates seeded'))
