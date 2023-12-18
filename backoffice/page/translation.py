from modeltranslation.translator import translator, TranslationOptions
from .models import StaticData, StaticDataItems

class StaticDataTranslation(TranslationOptions):
    fields = ('title',)

translator.register(StaticData, StaticDataTranslation)


class StaticDataItemsTranslation(TranslationOptions):
    fields = ('content', 'title')

translator.register(StaticDataItems, StaticDataItemsTranslation)


