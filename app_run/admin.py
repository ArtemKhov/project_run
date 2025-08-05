from django.contrib import admin

from app_run.models import Run, AthleteInfo, Challenge, Position, CollectibleItem, Subscription, Rating


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    """
    Административная панель для управления забегами.
    
    Отображает информацию о забегах атлетов с возможностью фильтрации
    по статусу, дате и атлету, а также поиска по комментариям.
    """
    
    list_display = ['id', 'athlete', 'status', 'distance', 'run_time_seconds', 'speed', 'created_at']
    list_filter = ['status', 'created_at', 'athlete']
    search_fields = ['athlete__username', 'athlete__first_name', 'athlete__last_name', 'comment']
    readonly_fields = ['created_at']
    ordering = ['-created_at']


@admin.register(AthleteInfo)
class AthleteInfoAdmin(admin.ModelAdmin):
    """
    Административная панель для управления информацией об атлетах.
    
    Позволяет просматривать и редактировать дополнительную информацию
    об атлетах: цели и вес.
    """
    
    list_display = ['user', 'weight', 'goals']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    list_filter = ['weight']


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    """
    Административная панель для управления вызовами/челленджами.
    
    Отображает вызовы с возможностью поиска по названию
    и фильтрации по атлету.
    """
    
    list_display = ['full_name', 'athlete']
    search_fields = ['full_name', 'athlete__username', 'athlete__first_name', 'athlete__last_name']
    list_filter = ['athlete']


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    """
    Административная панель для управления GPS позициями.
    
    Отображает координаты, время и метрики позиций с возможностью
    фильтрации по времени и атлету.
    """
    
    list_display = ['id', 'run', 'latitude', 'longitude', 'date_time', 'speed', 'distance']
    list_filter = ['date_time', 'run__athlete']
    search_fields = ['run__athlete__username', 'run__athlete__first_name', 'run__athlete__last_name']
    readonly_fields = ['date_time']
    ordering = ['-date_time']


@admin.register(CollectibleItem)
class CollectibleItemAdmin(admin.ModelAdmin):
    """
    Административная панель для управления коллекционными предметами.
    
    Позволяет управлять предметами, которые можно собрать во время забегов,
    с удобным виджетом для выбора пользователей.
    """
    
    list_display = ['name', 'uid', 'value', 'latitude', 'longitude', 'picture']
    search_fields = ['name', 'uid']
    list_filter = ['value']
    filter_horizontal = ['users']


@admin.register(Subscription)
class SubscribeAdmin(admin.ModelAdmin):
    """
    Административная панель для управления подписками атлетов на тренеров.
    
    Отображает подписки с информацией об активности и возможностью
    фильтрации по различным критериям.
    """
    
    list_display = ['athlete', 'coach', 'created_at', 'is_active']
    list_filter = ['is_active', 'created_at', 'athlete', 'coach']
    search_fields = ['athlete__username', 'coach__username', 'athlete__first_name', 'coach__first_name']
    readonly_fields = ['created_at']
    ordering = ['-created_at']


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    """
    Административная панель для управления оценками тренеров.
    
    Позволяет просматривать оценки, которые атлеты дают тренерам,
    с возможностью фильтрации по рейтингу и участникам.
    """
    
    list_display = ['athlete', 'coach', 'rating']
    list_filter = ['rating', 'athlete', 'coach']
    search_fields = ['athlete__username', 'coach__username', 'athlete__first_name', 'coach__first_name']
    ordering = ['-rating']
