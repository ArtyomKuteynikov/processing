# Generated by Django 4.2.5 on 2023-11-30 10:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0007_alter_invitecodes_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='method_2fa',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='customer',
            name='password',
            field=models.CharField(blank=True, max_length=1024, null=True),
        ),
        migrations.AlterField(
            model_name='customer',
            name='value_2fa',
            field=models.CharField(blank=True, max_length=1024, null=True),
        ),
    ]
