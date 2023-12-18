from django.db import models
from django.utils.text import slugify
from ckeditor.fields import RichTextField
# Create your models here.
class StaticData(models.Model):
    title = models.CharField(max_length=255)
    slug = models.CharField(unique=True)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.title}'
    
    class Meta:
        ordering = ['order']
    
    def dict(self):
        return {
            'id': self.id
        }
    
class StaticDataItems(models.Model):
    model = models.ForeignKey(StaticData, on_delete=models.SET_NULL, null=True, blank=False, related_name='staticdata_items')
    title = models.CharField(max_length=255, null=True, blank=False)
    content = RichTextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.model.title}'
