# Generated by Django 5.1.7 on 2025-03-23 12:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_booking_is_cancelled'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='was_verified_as_agent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='was_verified_as_investor',
            field=models.BooleanField(default=False),
        ),
    ]
