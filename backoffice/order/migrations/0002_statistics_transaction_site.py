# Generated by Django 4.2.5 on 2023-11-28 18:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0003_merchants_traders'),
        ('order', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Statistics',
            fields=[
            ],
            options={
                'verbose_name': 'Statistics',
                'verbose_name_plural': 'Statistics',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('order.transaction',),
        ),
        migrations.AddField(
            model_name='transaction',
            name='site',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='customer.websites'),
        ),
    ]
