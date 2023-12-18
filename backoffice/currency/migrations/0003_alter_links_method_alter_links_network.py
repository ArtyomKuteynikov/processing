# Generated by Django 4.2.5 on 2023-12-08 10:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('currency', '0002_alter_exchangedirection_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='links',
            name='method',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='currency.paymentmethods'),
        ),
        migrations.AlterField(
            model_name='links',
            name='network',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='currency.networks'),
        ),
    ]
