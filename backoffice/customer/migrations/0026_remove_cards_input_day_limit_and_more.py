# Generated by Django 4.2.5 on 2023-12-18 03:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0025_traderexchangedirections_cards'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cards',
            name='input_day_limit',
        ),
        migrations.RemoveField(
            model_name='cards',
            name='input_month_limit',
        ),
        migrations.RemoveField(
            model_name='cards',
            name='input_operation_limit',
        ),
        migrations.RemoveField(
            model_name='cards',
            name='output_dat_limit',
        ),
        migrations.RemoveField(
            model_name='cards',
            name='output_month_limit',
        ),
        migrations.RemoveField(
            model_name='cards',
            name='output_operation_limit',
        ),
        migrations.CreateModel(
            name='CardsLimits',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('input_operation_limit', models.IntegerField()),
                ('input_day_limit', models.IntegerField()),
                ('input_month_limit', models.IntegerField()),
                ('output_operation_limit', models.IntegerField()),
                ('output_dat_limit', models.IntegerField()),
                ('output_month_limit', models.IntegerField()),
                ('card', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='customer.cards')),
            ],
            options={
                'verbose_name': 'Card limits',
                'verbose_name_plural': 'Cards limits',
                'db_table': 'customer_cardslimits',
            },
        ),
    ]