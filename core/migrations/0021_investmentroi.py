# Generated by Django 5.1.7 on 2025-03-23 14:53

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_investment_tx_ref'),
    ]

    operations = [
        migrations.CreateModel(
            name='InvestmentROI',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('date_paid', models.DateField(auto_now_add=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('investment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rois', to='core.investment')),
            ],
        ),
    ]
