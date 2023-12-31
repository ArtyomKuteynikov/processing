# Generated by Django 4.2.5 on 2023-11-25 20:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('currency', '0001_initial'),
        ('customer', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.FloatField()),
                ('finished', models.BooleanField()),
                ('status', models.IntegerField(choices=[(0, 'New'), (1, 'Success'), (2, 'Froze at sender'), (3, 'Froze ar receiver'), (4, 'Canceled')])),
                ('counted', models.CharField(choices=[('-2', 'Not counted at sender'), ('-1', 'Not counted at receiver'), ('0', 'Not counted'), ('1', 'Counted'), ('2', 'In counting process')], max_length=2)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('other_id_1', models.IntegerField()),
                ('other_id_2', models.IntegerField()),
                ('category', models.CharField(max_length=128)),
                ('link', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='currency.links')),
                ('receiver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='receiver', to='customer.customer')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transaction_sender', to='customer.customer')),
            ],
            options={
                'verbose_name': 'Transaction',
                'verbose_name_plural': 'Transactions',
                'db_table': 'order_transaction',
                'ordering': ('created',),
            },
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('input_amount', models.FloatField(null=True)),
                ('output_amount', models.FloatField(null=True)),
                ('status', models.IntegerField(choices=[(0, 'New'), (1, 'Trader found'), (2, 'Marked as payed'), (3, 'Success'), (4, 'Declined'), (5, 'Timeout at user'), (6, 'Timeout at trader'), (7, 'Canceled by user'), (8, 'Partially or incorrect payment'), (9, 'Solved partially or incorrect payment by support'), (10, 'Complaint'), (11, 'Solved to sender'), (12, 'Solved to trader')])),
                ('comment', models.CharField(max_length=1024)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('input_link', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='order_input', to='currency.links')),
                ('output_link', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='order_output', to='currency.links')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='order_sender', to='customer.customer')),
                ('trader', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trader', to='customer.customer')),
            ],
            options={
                'verbose_name': 'Order',
                'verbose_name_plural': 'Orders',
                'db_table': 'order_order',
                'ordering': ('created',),
            },
        ),
    ]
