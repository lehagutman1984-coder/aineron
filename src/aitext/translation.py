"""
Переводимые поля контента каталога (django-modeltranslation).

Источник — русские поля (MODELTRANSLATION_DEFAULT_LANGUAGE='ru'), английские
колонки *_en заполняются командой `translate_catalog` (LLM через laozhang).
Какой язык отдаёт API, определяет LANGUAGE_CODE инстанса (ru / en при INTL_MODE),
fallback на ru при пустом переводе.
"""
from modeltranslation.translator import TranslationOptions, register

from .models import Category, FAQ, NeuralNetwork


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ('name',)


@register(NeuralNetwork)
class NeuralNetworkTranslationOptions(TranslationOptions):
    fields = ('description', 'seo_title', 'seo_description', 'seo_keywords')


@register(FAQ)
class FAQTranslationOptions(TranslationOptions):
    fields = ('question', 'answer')
