from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('app_run', '0008_position'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='position',
            unique_together=set(),
        ),
    ]