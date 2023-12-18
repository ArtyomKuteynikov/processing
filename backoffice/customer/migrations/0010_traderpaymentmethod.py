# Generated by Django 4.2.5 on 2023-12-05 05:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('currency', '0002_alter_exchangedirection_options'),
        ('customer', '0009_alter_customer_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='TraderPaymentMethod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_details', models.CharField(max_length=256)),
                ('initials', models.CharField(max_length=256)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='customer.customer')),
                ('method', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='currency.paymentmethods')),
            ],
        ),
    ]
