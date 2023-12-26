# Generated by Django 4.2.5 on 2023-12-25 14:34

import customer.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0038_alter_request_expiry'),
    ]

    operations = [
        migrations.AlterField(
            model_name='request',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='customer.websitescategories', verbose_name='Категория'),
        ),
        migrations.AlterField(
            model_name='request',
            name='expiry',
            field=models.DateField(default=customer.models.default_expiry),
        ),
    ]
