# Generated by Django 4.2.5 on 2023-12-08 21:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0014_rename_passport_scan_customerdocument_passport_scan_1_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='telegram_name',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
    ]