# Generated by Django 4.2.5 on 2023-11-29 18:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0006_request_alter_invitecodes_account'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invitecodes',
            name='code',
            field=models.CharField(max_length=15),
        ),
    ]
