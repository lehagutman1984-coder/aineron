"""
Проверяет, отдаёт ли провайдер usage в стриме (stream_options.include_usage)
для аудированных моделей — обязательный шаг ДО включения
TOKEN_METERING_STREAM_USAGE_MODELS на веб-SSE-пути
(TOKEN_OVERAGE_BILLING_PLAN.md, Спринт 1, задача 4/5).

laozhang.ai — реселлер, соблюдение OpenAI-контракта для stream_options
нельзя предполагать без проверки: 400 на этом параметре у необорачиваемого
в try вызова стрима в chats.py уронит SSE на проде под флагом, который
считается «безопасным».

Запуск: docker-compose exec web python manage.py probe_stream_usage
"""
from django.core.management.base import BaseCommand

from aitext.models import NeuralNetwork
from aitext.tasks import get_client_for_network

AUDITED_MODELS = [
    # Исходные 3 (уже в TOKEN_METERING_STREAM_USAGE_MODELS, реаудит не помешает).
    'claude-fable-5', 'claude-opus-4-8', 'claude-opus-5',
    'gpt-5.6-terra',
    # gpt-5-pro/gpt-5.4-pro/gpt-5.3 — не в текущем активном каталоге, убраны из
    # проверки (probe их всё равно пометит "НЕ НАЙДЕНА"), ставки в
    # core/model_pricing.py оставлены безвредно на случай возврата под этим именем.
    # 2026-09-28 (ITEM 1, часть A): расширение MODEL_WHOLESALE/TOKEN_OVERAGE_MODELS -
    # эти модели ещё не проверены на потоковый usage перед включением
    # TOKEN_METERING_STREAM_USAGE_MODELS для веб-SSE.
    'claude-fable-5.1', 'gpt-5.5-pro', 'gpt-6-astra', 'gpt-5.5',
    'claude-sonnet-4-6', 'gemini-3.1-pro-preview', 'claude-sonnet-5',
    'gpt-5.6-sol', 'grok-4.6', 'grok-4.5', 'qwen3.8-max',
]


class Command(BaseCommand):
    help = "Проверяет usage в стриме (stream_options) по 7 аудированным моделям"

    def handle(self, *args, **options):
        self.stdout.write("Проверка usage в стриме (stream_options.include_usage)\n" + "=" * 70)
        rows = []
        for model_name in AUDITED_MODELS:
            network = NeuralNetwork.objects.filter(model_name=model_name, is_active=True).first()
            if network is None:
                rows.append((model_name, 'НЕ НАЙДЕНА в БД', '-', '-'))
                continue
            try:
                client = get_client_for_network(network)
                usage = None
                chunk_count = 0
                with client.chat.completions.create(
                    model=model_name,
                    messages=[{'role': 'user', 'content': 'ping'}],
                    max_tokens=8,
                    stream=True,
                    stream_options={'include_usage': True},
                ) as stream:
                    for chunk in stream:
                        chunk_count += 1
                        if getattr(chunk, 'usage', None):
                            usage = chunk.usage
                if usage:
                    rows.append((model_name, 'OK', f'{usage.prompt_tokens}/{usage.completion_tokens}', f'{chunk_count} чанков'))
                else:
                    rows.append((model_name, 'НЕТ USAGE', '-', f'{chunk_count} чанков'))
            except Exception as e:
                rows.append((model_name, f'ОШИБКА: {str(e)[:60]}', '-', '-'))

        self.stdout.write(f"\n{'Модель':<22} {'Результат':<28} {'in/out':<12} {'Чанков'}")
        self.stdout.write('-' * 78)
        for model_name, status, tokens, chunks in rows:
            status_padded = f"{status:<28}"
            styled = self.style.SUCCESS(status_padded) if status == 'OK' else self.style.ERROR(status_padded)
            self.stdout.write(f"{model_name:<22} {styled} {tokens:<12} {chunks}")

        self.stdout.write('\n' + '=' * 78)
        self.stdout.write(
            "OK-модели можно добавить в TOKEN_METERING_STREAM_USAGE_MODELS (.env, "
            "через запятую) — только их SSE-путь начнёт запрашивать usage.\n"
            "Внимание: фолбэк-клиент (aitext/providers.py) может незаметно "
            "подменить фактического провайдера (laozhang→apimart) — если "
            "результат для какой-то модели неожиданный, проверь логи "
            "celery/web на '[providers] ... Фолбэк →' за это время."
        )
