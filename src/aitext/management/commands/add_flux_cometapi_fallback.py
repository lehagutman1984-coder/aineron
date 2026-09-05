"""
Проставляет CometAPI-резерв для FLUX.2 (flux-2-pro, flux-2-max, flux-2-flex).
У Kontext (flux-kontext-pro/-max) резерва нет — CometAPI не продаёт эту
линейку вообще, только FLUX.2.

metadata.cometapi_contract='flux' переключает точку фолбэка в
generate_with_falai() на generate_image_flux_cometapi() (отдельный контракт:
POST https://api.cometapi.com/flux/v1/{model}, НЕ /v1/images/generations).
metadata.cometapi_fallback_model — имя модели у CometAPI (совпадает с нашим).

ВАЖНО: первая попытка проверить этот путь (2026-09-06) сделала неверный
вывод "ненадёжно", потому что опрос статуса останавливался через 60-90с, а
задача реально завершается ~за 100с (подтверждено повторной проверкой с
более длинным опросом и по официальной документации CometAPI). Резерв
подключается с MAX_ATTEMPTS=60 при шаге 5с (~5 минут запаса).

Запуск: docker-compose exec web python manage.py add_flux_cometapi_fallback
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

SLUGS = ['flux-2-pro', 'flux-2-max', 'flux-2-flex']


class Command(BaseCommand):
    help = "Проставляет cometapi_contract='flux' + cometapi_fallback_model для FLUX.2 Pro/Max/Flex"

    def handle(self, *args, **options):
        for slug in SLUGS:
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена в БД, пропуск'))
                continue
            config = network.config_json or {}
            metadata = config.setdefault('metadata', {})
            changed = False
            if metadata.get('cometapi_contract') != 'flux':
                metadata['cometapi_contract'] = 'flux'
                changed = True
            if metadata.get('cometapi_fallback_model') != network.model_name:
                metadata['cometapi_fallback_model'] = network.model_name
                changed = True
            if not changed:
                self.stdout.write(f'{slug}: уже проставлено, пропуск')
                continue
            network.config_json = config
            network.save(update_fields=['config_json'])
            self.stdout.write(self.style.SUCCESS(f'{slug}: cometapi_contract=flux, fallback_model={network.model_name}'))
