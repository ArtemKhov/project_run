# Generated by Django 5.2 on 2025-07-27 10:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_run', '0011_collectibleitem'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collectibleitem',
            name='uid',
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
