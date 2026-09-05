"""
Заменяет DALL-E 3 на Midjourney в каталоге изображений — по прямому запросу
пользователя 2026-09-06: "убери модели [без рабочего провайдера], если
резерва нет оставь без резерва, главное чтобы работала модель хотя бы от
одного провайдера".

DALL-E 3 — единственная из 23 моделей каталога, у которой НЕТ рабочего пути
ни через APIMart, ни через CometAPI (проверено живьём: APIMart её не
продаёт вообще, CometAPI — 503 "no available channel", DALL-E закрытая
модель OpenAI, её нет и на Replicate). Деактивируется (is_active=False, не
удаляется — сохраняет историю чатов).

Midjourney — выбрана заменой, потому что это ЕДИНСТВЕННАЯ топовая модель,
которой не было в каталоге и которая есть одновременно у APIMart И у
CometAPI (настоящий резерв, не просто единственный провайдер). Оба
контракта проверены живыми вызовами 2026-09-06:
  APIMart:  POST /v1/midjourney/generations -> task_id -> GET /v1/tasks/{id}
            -> result.images[].url (4 отдельные картинки), завершилось за
            ~106с, cost=$0.04504 (relax-тир)
  CometAPI: POST /mj/submit/imagine -> result(task_id) ->
            GET /mj/task/{id}/fetch -> imageUrl (одна сетка 2×2),
            завершилось за ~70с

Цена: конкурент (Gen-API, RouterAI Midjourney не продаёт) — 7₽ за версию
5.*/6.* (genapi.txt). Целевая цена = 7₽ × 0.95 = 6.65₽. Пол по марже:
опт APIMart $0.04504 × 80 × 1.05 = 3.78₽ — цель выше пола, применяется
цель без изменений.

Запуск: docker-compose exec web python manage.py replace_dalle3_with_midjourney
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork, Category

MIDJOURNEY_CONFIG = {
    "name": "Midjourney",
    "api_defaults": {},
    "ui_settings": {"sections": []},
    "constraints": {},
    "metadata": {
        "output_type": "image",
        "minimal_params": True,
        "requires_input_images": False,
        "image_api": "apimart_async",
        "apimart_endpoint": "midjourney/generations",
        "cometapi_contract": "midjourney",
        "cometapi_fallback_model": "midjourney",
    },
}


class Command(BaseCommand):
    help = "Деактивирует DALL-E 3 (нет рабочего провайдера) и добавляет Midjourney (есть у APIMart и CometAPI)"

    def handle(self, *args, **options):
        dalle = NeuralNetwork.objects.filter(slug='dall-e-3').first()
        if dalle:
            dalle.is_active = False
            dalle.save(update_fields=['is_active'])
            self.stdout.write(self.style.SUCCESS('dall-e-3: деактивирована (is_active=False)'))
        else:
            self.stdout.write(self.style.WARNING('dall-e-3: не найдена, пропуск деактивации'))

        image_cat = Category.objects.filter(slug='images').first() or Category.objects.filter(name='Изображения').first()
        if not image_cat:
            self.stdout.write(self.style.ERROR('Категория "Изображения" не найдена — отменено'))
            return

        max_order = NeuralNetwork.objects.filter(category=image_cat).order_by('-order').first()
        next_order = (max_order.order + 1) if max_order else 1

        network, created = NeuralNetwork.objects.update_or_create(
            slug='midjourney',
            defaults={
                'name': 'Midjourney',
                'category': image_cat,
                'model_name': 'midjourney',
                'cost_per_message': 7,
                'cost_kopecks': 665,
                'order': next_order,
                'description_ru': 'Художественная генерация изображений — 4 варианта за один запрос.',
                'provider': 'fal-ai',
                'config_json': MIDJOURNEY_CONFIG,
                'is_active': True,
                'is_popular': True,
            }
        )
        status = 'создана' if created else 'обновлена'
        self.stdout.write(self.style.SUCCESS(f'midjourney: {status} (cost_kopecks=665, order={network.order})'))
