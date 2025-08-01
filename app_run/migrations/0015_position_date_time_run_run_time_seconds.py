# Generated by Django 5.2 on 2025-07-28 11:27

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_run', '0014_rename_items_collectibleitem_users'),
    ]

    operations = [
        migrations.AddField(
            model_name='position',
            name='date_time',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='run',
            name='run_time_seconds',
            field=models.IntegerField(default=0),
        ),
    ]
