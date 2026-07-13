"""Включает translate_to_english для уже задеплоенных Flux-моделей.

Причина (найдено 2026-07-13, эмпирически на реальном фото пользователя):
Flux/BFL (flux-2-pro, flux-2-max, flux-kontext-pro, flux-kontext-max,
flux-2-flex) плохо следует промтам не на английском при редактировании
фото — на русский промт "поменяй причёску" модель нередко возвращает
исходное фото практически без изменений. Тот же промт на английском
работает корректно. GPT Image/Gemini с русским справляются нормально.

Канонический источник — add_laozhang_models.py (там же добавлено в
defaults для новых/пересеиваемых строк). Эта команда — для строк,
созданных до фикса, так как add_laozhang_models не запускается
автоматически при каждом деплое.

Безопасно и идемпотентно — повторный запуск ничего не ломает.
"""
from django.core.management.base import BaseCommand

from aitext.models import NeuralNetwork
from aitext.management.commands.add_laozhang_models import FLUX_MODEL_SLUGS


class Command(BaseCommand):
    help = 'Включает translate_to_english для Flux-моделей (img2img на русском не работал)'

    def handle(self, *args, **options):
        qs = NeuralNetwork.objects.filter(slug__in=FLUX_MODEL_SLUGS, translate_to_english=False)

        if not qs.exists():
            self.stdout.write('Все Flux-модели уже с translate_to_english=True (или не найдены).')
            return

        updated = qs.update(translate_to_english=True)
        for network in NeuralNetwork.objects.filter(slug__in=FLUX_MODEL_SLUGS):
            self.stdout.write(f'  {network.name} ({network.slug}): translate_to_english={network.translate_to_english}')

        self.stdout.write(f'\nГотово! Обновлено моделей: {updated}')
