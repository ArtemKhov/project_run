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

