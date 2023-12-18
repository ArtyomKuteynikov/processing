from django.contrib import admin
from .models import StaticData, StaticDataItems
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline, TabbedTranslationAdmin,\
TranslationStackedInline
from adminsortable2.admin import SortableAdminMixin, SortableStackedInline


# Register your models here.

class StaticDataItemsInline(SortableStackedInline, TranslationStackedInline):
    model = StaticDataItems
    min_num = 1
    extra = 0

@admin.register(StaticData)
class StaticDataAdmin(SortableAdminMixin, TabbedTranslationAdmin):
    list_display = ('title', 'slug', 'order')
    list_editable = ['order',]
    fields = ('title', 'slug')
    inlines = [StaticDataItemsInline, ]
    
