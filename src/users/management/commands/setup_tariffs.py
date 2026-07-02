"""
Установка конкурентной тарифной сетки (рублёвый биллинг, 1 ₽ = 100 коп.).

Позиционирование (июль 2026): вход дешевле всех российских топов
(BotHub 200 ₽, ChadGPT 290 ₽, GoGPT 490 ₽, GPTunnel 990 ₽),
средние тарифы — на уровне или ниже при большем бонусе на баланс.

Идемпотентна: повторный запуск обновляет цены существующих тарифов
(поиск по display_name). Остальные активные платные тарифы деактивируются
(скрываются из покупки; подписки пользователей не трогаются) —
отключается флагом --keep-others.
"""
from django.core.management.base import BaseCommand

from users.models import Tariff

# display_name -> (цена ₽/мес, начисление на баланс ₽, реф. бонус ₽, описание)
TARIFFS = [
    ('Старт', 149, 170, 15,
     'Для знакомства: 170 ₽ на балансе — это ~170 ответов DeepSeek или ~40 ответов GPT-4o.'),
    ('Стандарт', 399, 480, 40,
     'Оптимум для повседневной работы: +20% бонус к пополнению, хватает на ~120 ответов GPT-4o.'),
    ('Про', 899, 1150, 90,
     'Для активных пользователей: +28% бонус, доступ ко всем моделям, включая GPT-5 и Claude Opus.'),
    ('Макс', 1990, 2800, 200,
     'Максимум выгоды: +40% бонус — 2800 ₽ на балансе для генерации текста, изображений и видео.'),
    # S5 (TELEGRAM_SUPREMACY_PLAN): AI-секретарь для Telegram Business
    ('Бизнес', 990, 500, 100,
     'AI-секретарь в Telegram Business: до 300 авто-ответов клиентам в месяц '
     '(сверх — 1 ₽/ответ) + 500 ₽ на баланс для чатов и генераций.'),
]


class Command(BaseCommand):
    help = 'Создаёт/обновляет конкурентную тарифную сетку (Старт/Стандарт/Про/Макс)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-others', action='store_true',
            help='Не деактивировать прочие активные платные тарифы',
        )

    def handle(self, *args, **options):
        # Бесплатный тариф: гарантируем существование (грант 10 ₽ при регистрации)
        free = Tariff.get_default_tariff()
        self.stdout.write(f'Бесплатный тариф: {free.display_name} (грант {free.pages_count} ₽)')

        keep_names = []
        for name, price, grant_rub, ref_bonus_rub, description in TARIFFS:
            tariff, created = Tariff.objects.update_or_create(
                display_name=name,
                defaults={
                    # pages_count хранит рубли (1 звезда legacy = 1 ₽);
                    # balance_grant_kopecks синхронизируется в Tariff.save() ×100
                    'pages_count': grant_rub,
                    'price': price,
                    'is_active': True,
                    'is_free': False,
                    'is_trial': False,
                    'duration_days': 30,
                    'referral_bonus_stars': ref_bonus_rub,
                    'description': description,
                },
            )
            keep_names.append(name)
            status = 'создан' if created else 'обновлён'
            bonus_pct = round((grant_rub - price) / price * 100)
            self.stdout.write(
                f'  {status}: {name} — {price} ₽/мес -> {grant_rub} ₽ на баланс '
                f'(+{bonus_pct}%), реф. бонус {ref_bonus_rub} ₽'
            )

        if not options['keep_others']:
            stale = Tariff.objects.filter(is_active=True, is_free=False).exclude(
                display_name__in=keep_names,
            )
            for t in stale:
                self.stdout.write(self.style.WARNING(
                    f'  деактивирован устаревший тариф: {t.display_name} ({t.price} ₽)'
                ))
            stale.update(is_active=False)

        self.stdout.write(self.style.SUCCESS('Готово. Тарифная сетка актуальна.'))
