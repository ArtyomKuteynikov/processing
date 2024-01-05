# Generated by Django 4.2.5 on 2023-12-27 21:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0043_alter_logs_user_agent'),
    ]

    operations = [
        migrations.CreateModel(
            name='Wallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hex_address', models.CharField(max_length=50)),
                ('address', models.CharField(max_length=40)),
                ('private_key', models.CharField(max_length=1024)),
                ('public_key', models.CharField(max_length=1024)),
            ],
        ),
        migrations.AddField(
            model_name='customer',
            name='wallet',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='customer.wallet'),
        ),
    ]
