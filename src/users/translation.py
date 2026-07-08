"""
Переводимые поля юридических документов (django-modeltranslation).

aineron.ru (LANGUAGE_CODE='ru') и aineron.net (LANGUAGE_CODE='en', INTL_MODE=1)
работают на РАЗНЫХ базах данных с разным содержимым — каждый инстанс
редактирует свою пару title_ru/content_ru или title_en/content_en независимо.
На aineron.net юр-документы не переведены с русского, а написаны заново без
персональных данных исполнителя (см. seed_intl_legal_docs) — крипта-оплата
международного инстанса не требует российских банковских реквизитов.
"""
from modeltranslation.translator import TranslationOptions, register

from .models import LegalDocument


@register(LegalDocument)
class LegalDocumentTranslationOptions(TranslationOptions):
    fields = ('title', 'content')
