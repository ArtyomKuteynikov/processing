# Generated by Django 4.2.5 on 2023-12-16 05:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0003_balance_frozen'),
    ]

    operations = [
        migrations.AlterField(
            model_name='withdrawal',
            name='comment',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
    ]