from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.models import User
from django.db import models

from rest_framework import serializers

from .models import Run, AthleteInfo, Challenge, Position, CollectibleItem, Rating


class UserSerializer(serializers.ModelSerializer):
    """
    Базовый сериализатор для пользователей.
    
    Предоставляет основные поля пользователя: ID, имя пользователя,
    фамилию и имя.
    """
    
    class Meta:
        model = User
        fields = ['id', 'username', 'last_name', 'first_name']


class UserChallengeSerializer(serializers.ModelSerializer):
    """
    Сериализатор для пользователей в контексте челленджей.
    
    Добавляет поле full_name, которое объединяет имя и фамилию пользователя.
    """
    
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'full_name', 'username']

    def get_full_name(self, obj):
        """Возвращает полное имя пользователя (имя + фамилия)."""
        return f"{obj.first_name} {obj.last_name}"


class RunSerializer(serializers.ModelSerializer):
    """
    Сериализатор для забегов.
    
    Включает данные об атлете через вложенный сериализатор
    и все основные поля забега.
    """
    
    athlete_data = UserSerializer(read_only=True, source='athlete')
    
    class Meta:
        model = Run
        fields = ['id',
                  'athlete_data',
                  'created_at',
                  'athlete',
                  'comment',
                  'status',
                  'distance',
                  'run_time_seconds',
                  'speed']


class AthleteInfoSerializer(serializers.ModelSerializer):
    """
    Сериализатор для дополнительной информации об атлетах.
    
    Предоставляет доступ к целям и весу атлета.
    """
    
    class Meta:
        model = AthleteInfo
        fields = ['user_id', 'goals', 'weight']


class RunnerSerializer(serializers.ModelSerializer):
    """
    Сериализатор для бегунов (пользователей).
    
    Добавляет вычисляемые поля: тип пользователя (атлет/тренер),
    количество завершенных забегов и средний рейтинг.
    """
    
    type = serializers.SerializerMethodField()
    runs_finished = serializers.ReadOnlyField()
    rating = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'date_joined', 'username', 'last_name', 'first_name', 'type', 'runs_finished', 'rating']

    def get_type(self, user):
        """Возвращает тип пользователя: 'coach' для тренеров, 'athlete' для атлетов."""
        return "coach" if user.is_staff else "athlete"

    def get_rating(self, user):
        """Возвращает средний рейтинг пользователя, округленный до 2 знаков."""
        rating = getattr(user, 'avg_rating', None)
        if rating is not None:
            return round(rating, 2)
        return None


class ChallengeSerializer(serializers.ModelSerializer):
    """
    Сериализатор для челленджей.
    
    Предоставляет название челленджа и связанного атлета.
    """
    
    class Meta:
        model = Challenge
        fields = ['full_name', 'athlete']


class PositionSerializer(serializers.ModelSerializer):
    """
    Сериализатор для GPS позиций.
    
    Включает валидацию координат и проверку статуса забега.
    Форматирует дату и время в ISO формате.
    """
    
    date_time = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%f')

    class Meta:
        model = Position
        fields = ['id', 'run', 'latitude', 'longitude', 'date_time', 'speed', 'distance']

    def validate_run(self, run):
        """Проверяет, что забег находится в статусе 'В процессе'."""
        if run.status != Run.Status.IN_PROGRESS:
            raise serializers.ValidationError("Забег должен быть в статусе 'В процессе'.")
        return run

    def validate_latitude(self, latitude):
        """Проверяет, что широта находится в допустимом диапазоне [-90.0, 90.0]."""
        if not (-90.0 <= latitude <= 90.0):
            raise serializers.ValidationError("Широта должна находиться в диапазоне [-90.0, 90.0] градусов.")
        return latitude

    def validate_longitude(self, longitude):
        """Проверяет, что долгота находится в допустимом диапазоне [-180.0, 180.0]."""
        if not (-180.0 <= longitude <= 180.0):
            raise serializers.ValidationError("Долгота должна находиться в диапазоне [-180.0, 180.0] градусов.")
        return longitude


class CollectibleItemSerializer(serializers.ModelSerializer):
    """
    Сериализатор для коллекционных предметов.
    
    Включает валидацию координат, UID, ценности и URL изображения.
    Поддерживает создание новых предметов.
    """
    
    class Meta:
        model = CollectibleItem
        fields = ['name', 'uid', 'value', 'latitude', 'longitude', 'picture']
        extra_kwargs = {
            'picture': {'required': False, 'allow_null': True, 'allow_blank': True}
        }

    def validate_uid(self, uid):
        """Проверяет, что UID передан и не пустой."""
        if not uid:
            raise serializers.ValidationError("UID не может быть пустым")
        return uid

    def validate_value(self, value):
        """Проверяет, что переданное значение - это число."""
        if not isinstance(value, int):
            raise serializers.ValidationError("Ожидается число")
        return value

    def validate_latitude(self, latitude):
        """Проверяет, что широта - это float число в диапазоне [-90.0, 90.0]."""
        try:
            float(latitude)
            if not (-90.0 <= latitude <= 90.0):
                raise serializers.ValidationError("Широта должна находиться в диапазоне [-90.0, 90.0] градусов.")
            return latitude
        except (ValueError, TypeError):
            raise serializers.ValidationError("Широта должна быть числом")

    def validate_longitude(self, longitude):
        """Проверяет, что долгота - это float число в диапазоне [-180.0, 180.0]."""
        try:
            float(longitude)
            if not (-180.0 <= longitude <= 180.0):
                raise serializers.ValidationError("Долгота должна находиться в диапазоне [-180.0, 180.0] градусов.")
            return longitude
        except (ValueError, TypeError):
            raise serializers.ValidationError("Долгота должна быть числом")

    def validate_picture(self, value):
        """Проверяет, что URL валиден (если он предоставлен)."""
        if value:
            validator = URLValidator()
            try:
                validator(value)
            except DjangoValidationError:
                raise serializers.ValidationError("Неверный URL формат")
        return value

    def create(self, validated_data):
        """Создает новый коллекционный предмет в базе данных."""
        return CollectibleItem.objects.create(**validated_data)


class CoachDetailSerializer(RunnerSerializer):
    """
    Детальный сериализатор для тренеров.
    
    Расширяет RunnerSerializer, добавляя список ID атлетов,
    подписанных на данного тренера.
    """
    
    athletes = serializers.SerializerMethodField()

    class Meta(RunnerSerializer.Meta):
        fields = RunnerSerializer.Meta.fields + ['athletes']

    def get_athletes(self, coach):
        """Возвращает список ID атлетов, подписанных на тренера."""
        return list(coach.coach_subscribers.filter(athlete__is_staff=False).values_list('athlete_id', flat=True))


class AthleteDetailSerializer(RunnerSerializer):
    """
    Детальный сериализатор для атлетов.
    
    Расширяет RunnerSerializer, добавляя ID тренера,
    на которого подписан атлет.
    """
    
    coach = serializers.SerializerMethodField()

    class Meta(RunnerSerializer.Meta):
        fields = RunnerSerializer.Meta.fields + ['coach']

    def get_coach(self, athlete):
        """Возвращает ID первого тренера, на которого подписан атлет."""
        subscription = athlete.athlete_subscriptions.filter(is_active=True, coach__is_staff=True).first()
        return subscription.coach_id if subscription else None


class RatingSerializer(serializers.ModelSerializer):
    """
    Сериализатор для оценок тренеров.
    
    Предоставляет поля для тренера, атлета и оценки.
    """
    
    class Meta:
        model = Rating
        fields = ['coach', 'athlete', 'rating']







