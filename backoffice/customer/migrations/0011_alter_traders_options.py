# Generated by Django 4.2.5 on 2023-12-05 05:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0010_traderpaymentmethod'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='traders',
            options={'verbose_name': 'Trader', 'verbose_name_plural': 'Traders'},
        ),
    ]
