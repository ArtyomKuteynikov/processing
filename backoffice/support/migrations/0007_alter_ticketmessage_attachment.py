# Generated by Django 4.2.5 on 2023-12-24 14:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0006_alter_ticketmessage_attachment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticketmessage',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to='support', verbose_name='message_attachment'),
        ),
    ]
