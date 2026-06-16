from django.core.management.base import BaseCommand
from studio.models import StudioTemplate

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
        for data in TEMPLATES:
            obj, created = StudioTemplate.objects.update_or_create(
                slug=data['slug'],
                defaults={k: v for k, v in data.items() if k != 'slug'},
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'{action}: {obj.name}')
        self.stdout.write(self.style.SUCCESS(f'Done: {len(TEMPLATES)} templates seeded'))
