# Generated by Django 4.2.5 on 2023-11-26 10:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketmessage',
            name='ticket',
            field=models.ForeignKey(default=2, on_delete=django.db.models.deletion.CASCADE, to='support.ticket'),
            preserve_default=False,
        ),
    ]
