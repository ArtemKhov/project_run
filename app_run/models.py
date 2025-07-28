from django.contrib.auth.models import User
from django.db import models


class Run(models.Model):
    class Status(models.TextChoices):
        INIT = 'init', 'Забег инициализирован'
        IN_PROGRESS = 'in_progress', 'Забег начат'
        FINISHED = 'finished', 'Забег закончен'

    created_at = models.DateTimeField(auto_now_add=True)
    athlete = models.ForeignKey(User, on_delete=models.CASCADE, related_name='runs')
    comment = models.TextField()
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.INIT)
    distance = models.FloatField(default=0.0)
    run_time_seconds = models.IntegerField()

class AthleteInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='athlete_info')
    goals = models.TextField(blank=True, default='')
    weight = models.IntegerField(blank=True, null=True)

class Challenge(models.Model):
    full_name = models.CharField(max_length=255)
    athlete = models.ForeignKey(User, on_delete=models.CASCADE, related_name='challenge')

class Position(models.Model):
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name='position')
    latitude = models.DecimalField(max_digits=10, decimal_places=4)
    longitude = models.DecimalField(max_digits=10, decimal_places=4)
    date_time = models.DateTimeField()

class CollectibleItem(models.Model):
    name = models.CharField(max_length=255)
    uid = models.CharField(max_length=255, unique=True)
    value = models.IntegerField(default=0)
    latitude = models.DecimalField(max_digits=10, decimal_places=4)
    longitude = models.DecimalField(max_digits=10, decimal_places=4)
    picture = models.URLField(blank=True, null=True)
    users = models.ManyToManyField(User, related_name='collectible_items')
