# Generated by Django 4.2.5 on 2023-12-26 13:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('currency', '0004_courses'),
    ]

    operations = [
        migrations.AddField(
            model_name='links',
            name='commission',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
    ]
