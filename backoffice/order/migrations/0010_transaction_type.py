# Generated by Django 4.2.5 on 2023-12-12 10:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0009_order_initials_order_payment_details_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='type',
            field=models.IntegerField(choices=[(0, 'Пополнение'), (1, 'Вывод')], default=1),
            preserve_default=False,
        ),
    ]