from django.utils import timezone
from django.core.exceptions import ValidationError

from django.contrib.auth.models import User
from django.db import models


class Run(models.Model):
    """
    Модель для хранения информации о забегах атлетов.
    Содержит данные о статусе забега, дистанции, времени и скорости.
    """
    
    class Status(models.TextChoices):
        INIT = 'init', 'Забег инициализирован'
        IN_PROGRESS = 'in_progress', 'Забег начат'
        FINISHED = 'finished', 'Забег закончен'

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    athlete = models.ForeignKey(User, on_delete=models.CASCADE, related_name='runs', verbose_name='Атлет')
    comment = models.TextField(verbose_name='Комментарий')
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.INIT, verbose_name='Статус')
    distance = models.FloatField(default=0.0, verbose_name='Дистанция (км)')
    run_time_seconds = models.IntegerField(default=0, verbose_name='Время забега (секунды)')
    speed = models.FloatField(default=0.0, verbose_name='Средняя скорость (км/ч)')

    def __str__(self):
        return f"Забег {self.id} - {self.athlete.username} ({self.get_status_display()})"

    class Meta:
        verbose_name = 'Забег'
        verbose_name_plural = 'Забеги'


class AthleteInfo(models.Model):
    """
    Модель для хранения дополнительной информации об атлетах.
    Содержит цели и вес атлета.
    """
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='athlete_info', verbose_name='Пользователь')
    goals = models.TextField(blank=True, default='', verbose_name='Цели')
    weight = models.IntegerField(blank=True, null=True, verbose_name='Вес (кг)')

    def __str__(self):
        return f"Информация о {self.user.username}"

    class Meta:
        verbose_name = 'Информация об атлете'
        verbose_name_plural = 'Информация об атлетах'


class Challenge(models.Model):
    """
    Модель для хранения информации о вызовах/челленджах.
    Содержит название вызова и связанного с ним атлета.
    """
    
    full_name = models.CharField(max_length=255, verbose_name='Название челленджа')
    athlete = models.ForeignKey(User, on_delete=models.CASCADE, related_name='challenge', verbose_name='Атлет')

    def __str__(self):
        return f"{self.full_name} - {self.athlete.username}"

    class Meta:
        verbose_name = 'Челлендж'
        verbose_name_plural = 'Челленджи'


class Position(models.Model):
    """
    Модель для хранения GPS позиций во время забега.
    Содержит координаты, время, скорость и дистанцию на момент записи позиции.
    """
    
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name='position', verbose_name='Забег')
    latitude = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='Широта')
    longitude = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='Долгота')
    date_time = models.DateTimeField(default=timezone.now, verbose_name='Дата и время')
    speed = models.FloatField(default=0.0, verbose_name='Скорость (км/ч)')
    distance = models.FloatField(default=0.0, verbose_name='Дистанция (км)')

    def __str__(self):
        return f"Позиция {self.id} - {self.run.athlete.username} ({self.date_time})"

    class Meta:
        verbose_name = 'Позиция'
        verbose_name_plural = 'Позиции'


class CollectibleItem(models.Model):
    """
    Модель для хранения коллекционных предметов.
    Содержит информацию о предметах, которые можно собрать во время забегов.
    """
    
    name = models.CharField(max_length=255, verbose_name='Название')
    uid = models.CharField(max_length=255, unique=True, verbose_name='Уникальный идентификатор')
    value = models.IntegerField(default=0, verbose_name='Ценность')
    latitude = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='Широта')
    longitude = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='Долгота')
    picture = models.URLField(blank=True, null=True, verbose_name='Изображение')
    users = models.ManyToManyField(User, related_name='collectible_items', verbose_name='Пользователи')

    def __str__(self):
        return f"{self.name} (UID: {self.uid})"

    class Meta:
        verbose_name = 'Коллекционный предмет'
        verbose_name_plural = 'Коллекционные предметы'


class Subscribe(models.Model):
    """
    Модель для хранения подписок атлетов на тренеров.
    Позволяет атлетам подписываться на тренеров для получения рекомендаций.
    """
    
    athlete = models.ForeignKey(User, on_delete=models.CASCADE, related_name='athlete_subscriptions', verbose_name='Атлет')
    coach = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coach_subscribers', verbose_name='Тренер')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата подписки')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    def __str__(self):
        return f"{self.athlete.username} → {self.coach.username}"

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        unique_together = ('athlete', 'coach')


class Rating(models.Model):
    """
    Модель для хранения оценок тренеров от атлетов.
    Позволяет атлетам оценивать тренеров по шкале от 1 до 5.
    """
    
    athlete = models.ForeignKey(User, on_delete=models.CASCADE, related_name='athlete_rating', verbose_name='Атлет')
    coach = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coach_rating', verbose_name='Тренер')
    rating = models.IntegerField(blank=True, null=True, verbose_name='Оценка')

    def clean(self):
        if self.rating is not None and (self.rating < 1 or self.rating > 5):
            raise ValidationError({'rating': 'Оценка должна быть от 1 до 5.'})

    def __str__(self):
        return f"{self.athlete.username} → {self.coach.username} ({self.rating}/5)"

    class Meta:
        verbose_name = 'Рейтинг'
        verbose_name_plural = 'Рейтинг'
        unique_together = ('athlete', 'coach')
