# Generated by Django 4.2.5 on 2023-12-05 08:15

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0011_alter_traders_options'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='traderpaymentmethod',
            options={'verbose_name': 'Trader payment method', 'verbose_name_plural': 'Trader payment methods'},
        ),
        migrations.AlterModelTable(
            name='traderpaymentmethod',
            table='customer_traderpaymentmethod',
        ),
    ]