from django.utils import timezone
from django.core.exceptions import ValidationError

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
    run_time_seconds = models.IntegerField(default=0)
    speed = models.FloatField(default=0.0)

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
    date_time = models.DateTimeField(default=timezone.now)
    speed = models.FloatField(default=0.0)
    distance = models.FloatField(default=0.0)

class CollectibleItem(models.Model):
    name = models.CharField(max_length=255)
    uid = models.CharField(max_length=255, unique=True)
    value = models.IntegerField(default=0)
    latitude = models.DecimalField(max_digits=10, decimal_places=4)
    longitude = models.DecimalField(max_digits=10, decimal_places=4)
    picture = models.URLField(blank=True, null=True)
    users = models.ManyToManyField(User, related_name='collectible_items')

class Subscribe(models.Model):
    athlete = models.ForeignKey(User, on_delete=models.CASCADE, related_name='athlete_subscriptions')
    coach = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coach_subscribers')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата подписки')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        unique_together = ('athlete', 'coach')

class Rating(models.Model):
    athlete = models.ForeignKey(User, on_delete=models.CASCADE, related_name='athlete_rating')
    coach = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coach_rating')
    rating = models.IntegerField(blank=True, null=True)

    def clean(self):
        if self.rating is not None and (self.rating < 1 or self.rating > 5):
            raise ValidationError({'rating': 'Оценка должна быть от 1 до 5.'})

    class Meta:
        verbose_name = 'Рейтинг'
        verbose_name_plural = 'Рейтинг'
        unique_together = ('athlete', 'coach')
