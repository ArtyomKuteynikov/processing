# Generated by Django 4.2.5 on 2023-11-25 20:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('currency', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_type', models.CharField(choices=[('MERCHANT', 'Merchant'), ('TRADER', 'Trader')], max_length=256)),
                ('account_status', models.CharField(choices=[('active', 'Active'), ('blocked', 'Blocked')], max_length=256)),
                ('status', models.CharField(choices=[('INIT', 'Initial'), ('BLOCKED', 'Blocked')], max_length=256)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('phone', models.CharField(blank=True, max_length=20, null=True)),
                ('email_is_verified', models.BooleanField(default=False)),
                ('phone_is_verified', models.BooleanField(default=False)),
                ('password', models.CharField(max_length=1024)),
                ('key', models.CharField(max_length=1024)),
                ('lang_code', models.CharField(max_length=10)),
                ('method_2fa', models.IntegerField()),
                ('value_2fa', models.CharField(max_length=1024)),
                ('time_zone', models.IntegerField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Customer',
                'verbose_name_plural': 'Customer',
                'db_table': 'customer',
                'ordering': ('email',),
            },
        ),
        migrations.CreateModel(
            name='Websites',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=128)),
                ('status', models.IntegerField(choices=[(0, 'New'), (1, 'Moderated'), (2, 'Declined')])),
                ('payment_method', models.IntegerField(choices=[(0, 'On system page'), (1, 'JS popup')])),
                ('verified', models.IntegerField(choices=[(0, 'Unverified'), (1, 'Verified')])),
                ('verification_code', models.CharField(max_length=64)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('currency', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='currency.currency')),
            ],
            options={
                'verbose_name': 'Website',
                'verbose_name_plural': 'Websites',
                'db_table': 'customer_websites',
                'ordering': ('created',),
            },
        ),
        migrations.CreateModel(
            name='InviteCodes',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.CharField(max_length=100)),
                ('code', models.IntegerField()),
                ('status', models.IntegerField(choices=[(0, 'New'), (1, 'Used'), (2, 'Deactivated')])),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='customer.customer')),
            ],
            options={
                'verbose_name': 'Invite code',
                'verbose_name_plural': 'Invite codes',
                'db_table': 'customer_invite_codes',
                'ordering': ('created',),
            },
        ),
        migrations.CreateModel(
            name='CustomerDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('file', models.FileField(blank=True, upload_to='documents')),
                ('type', models.CharField(choices=[('id', 'ID'), ('passport', 'PASSPORT'), ('residence', 'RESIDENCE_PERMIT')], max_length=100)),
                ('document_number', models.CharField(max_length=100)),
                ('issue_date', models.DateField()),
                ('expiry_date', models.DateField()),
                ('data', models.CharField(max_length=1000)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='customer.customer')),
            ],
            options={
                'verbose_name': 'Customer document',
                'verbose_name_plural': 'Customer documents',
                'db_table': 'customer_documents',
                'ordering': ('created',),
            },
        ),
    ]
