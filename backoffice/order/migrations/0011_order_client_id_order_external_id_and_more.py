# Generated by Django 4.2.5 on 2023-12-12 11:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0010_transaction_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='client_id',
            field=models.IntegerField(default=12543),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='external_id',
            field=models.IntegerField(default=15734),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='transaction',
            name='category',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='other_id_1',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='other_id_2',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]