"""
Регистрирует все Celery Beat периодические задачи через DatabaseScheduler.
Запускается один раз после деплоя: python manage.py setup_periodic_tasks
Повторный запуск безопасен — обновляет существующие записи.
"""
from django.core.management.base import BaseCommand


TASKS = [
    {
        "name": "Ежедневные AI-дайджесты (каждую минуту)",
        "task": "telegram_bot.tasks.send_daily_digests",
        "schedule": {"minute": "*"},
        "cron": True,
    },
    {
        "name": "Напоминания (каждую минуту)",
        "task": "telegram_bot.tasks.send_reminders",
        "schedule": {"minute": "*"},
        "cron": True,
    },
    {
        "name": "AI-задачи по расписанию (каждую минуту)",
        "task": "telegram_bot.tasks.run_due_ai_tasks",
        "schedule": {"minute": "*"},
        "cron": True,
    },
    {
        "name": "Уведомление о низком балансе (ежедневно в 10:00 МСК)",
        "task": "telegram_bot.tasks.notify_low_balance",
        "schedule": {"hour": "7", "minute": "0"},  # UTC 07:00 = MSK 10:00
        "cron": True,
    },
    {
        "name": "AI-секретарь: утренняя сводка (ежедневно 09:00 МСК)",
        "task": "telegram_bot.tasks.business_daily_summary",
        "schedule": {"hour": "6", "minute": "0"},  # UTC 06:00 = MSK 09:00
        "cron": True,
    },
    {
        "name": "AI-секретарь: очистка черновиков старше 7 дней (ежедневно)",
        "task": "telegram_bot.tasks.cleanup_business_drafts",
        "schedule": {"hour": "2", "minute": "30"},
        "cron": True,
    },
    {
        "name": "Группы: очистка логов /summary старше 48 ч (ежедневно)",
        "task": "telegram_bot.tasks.cleanup_group_message_logs",
        "schedule": {"hour": "3", "minute": "0"},
        "cron": True,
    },
    {
        "name": "Подарки за активность (понедельник 12:00 МСК, за флагом TG_GIFTS)",
        "task": "telegram_bot.tasks.send_activity_gifts",
        "schedule": {"day_of_week": "1", "hour": "9", "minute": "0"},  # UTC 09:00 = MSK 12:00
        "cron": True,
    },
    {
        "name": "Сброс ежемесячной квоты Billing seats (1-го числа в 00:00 UTC)",
        "task": "api.tasks.reset_monthly_seats",
        "schedule": {"day_of_month": "1", "hour": "0", "minute": "0"},
        "cron": True,
    },
]


class Command(BaseCommand):
    help = "Register/update all Celery Beat periodic tasks in the database"

    def handle(self, *args, **options):
        from django_celery_beat.models import CrontabSchedule, PeriodicTask
        import json

        created_count = 0
        updated_count = 0

        for cfg in TASKS:
            schedule_data = cfg["schedule"]
            crontab, _ = CrontabSchedule.objects.get_or_create(
                minute=schedule_data.get("minute", "0"),
                hour=schedule_data.get("hour", "*"),
                day_of_week=schedule_data.get("day_of_week", "*"),
                day_of_month=schedule_data.get("day_of_month", "*"),
                month_of_year=schedule_data.get("month_of_year", "*"),
            )
            task_name = cfg["name"]
            task_func = cfg["task"]

            obj, created = PeriodicTask.objects.update_or_create(
                name=task_name,
                defaults={
                    "task": task_func,
                    "crontab": crontab,
                    "enabled": True,
                    "kwargs": json.dumps({}),
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f"  [+] {task_name}")
            else:
                updated_count += 1
                self.stdout.write(f"  [=] {task_name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_count} created, {updated_count} updated."
            )
        )
