# Generated by Django 4.2.5 on 2023-12-25 15:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0014_order_bank_order_card_number_order_initials'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='client_contact',
            field=models.CharField(blank=True, max_length=256, null=True),
        ),
    ]
