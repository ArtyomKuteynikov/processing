# Generated by Django 4.2.5 on 2023-12-05 08:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0006_order_method_order_uuid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='uuid',
            field=models.CharField(max_length=128),
        ),
    ]
