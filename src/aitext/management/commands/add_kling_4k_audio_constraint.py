"""
Закрывает пункт из аудита update_video_pricing: у Kling v3 / v3 Omni /
v3 Motion Control CometAPI явно указывает, что 4K доступен ТОЛЬКО без звука
(со звуком — максимум 1080p, см. docstring update_video_pricing.py). Раньше
это нигде не проверялось — можно было выбрать mode=4k и включить audio
одновременно, система просто складывала обе доплаты, хотя такой комбинации
не существует ни в прайсе, ни (вероятно) в самом апстриме.

Добавляет constraints.incompatible в config_json трёх моделей — проверяется
в validate_and_merge_settings() (src/aitext/fal_utils.py).

Запуск: docker-compose exec web python manage.py add_kling_4k_audio_constraint
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

SLUGS = ['kling-v3', 'kling-v3-omni', 'kling-v3-motion-control']

RULE = {
    "when": {"field": "mode", "value": "4k"},
    "forbid": {"field": "audio", "value": True},
    "message": "4K доступен только без звука — выберите 720p/1080p для звуковой генерации",
}


class Command(BaseCommand):
    help = "Добавляет constraints.incompatible (4K + звук) для Kling v3/Omni/Motion Control"

    def handle(self, *args, **options):
        for slug in SLUGS:
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена, пропуск'))
                continue
            config = network.config_json or {}
            constraints = config.setdefault('constraints', {})
            existing = constraints.setdefault('incompatible', [])
            if any(r.get('when') == RULE['when'] and r.get('forbid') == RULE['forbid'] for r in existing):
                self.stdout.write(f'{slug}: правило уже есть, пропуск')
                continue
            existing.append(RULE)
            network.config_json = config
            network.save(update_fields=['config_json'])
            self.stdout.write(self.style.SUCCESS(f'{slug}: добавлено'))
