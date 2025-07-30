from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Run, AthleteInfo, Challenge, Position, CollectibleItem, Rating
from django.db import models


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'last_name', 'first_name']


class UserChallengeSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'full_name', 'username']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class RunSerializer(serializers.ModelSerializer):
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
    class Meta:
        model = AthleteInfo
        fields = ['user_id', 'goals', 'weight']


class RunnerSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    runs_finished = serializers.ReadOnlyField()
    rating = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'date_joined', 'username', 'last_name', 'first_name', 'type', 'runs_finished', 'rating']

    def get_type(self, user):
        return "coach" if user.is_staff else "athlete"

    def get_rating(self, user):
        rating = getattr(user, 'avg_rating', None)
        if rating is not None:
            return round(rating, 2)
        return None


class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = ['full_name', 'athlete']


class PositionSerializer(serializers.ModelSerializer):
    date_time = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%f')

    class Meta:
        model = Position
        fields = ['id', 'run', 'latitude', 'longitude', 'date_time', 'speed', 'distance']

    def validate_run(self, run):
        if run.status != Run.Status.IN_PROGRESS:
            raise serializers.ValidationError("Забег должен быть в статусе 'В процессе'.")
        return run

    def validate_latitude(self, latitude):
        if not (-90.0 <= latitude <= 90.0):
            raise serializers.ValidationError("Широта должна находиться в диапазоне [-90.0, 90.0] градусов.")
        return latitude

    def validate_longitude(self, longitude):
        if not (-180.0 <= longitude <= 180.0):
            raise serializers.ValidationError("Долгота должна находиться в диапазоне [-180.0, 180.0] градусов.")
        return longitude


class CollectibleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectibleItem
        fields = ['name', 'uid', 'value', 'latitude', 'longitude', 'picture']
        extra_kwargs = {
            'picture': {'required': False, 'allow_null': True, 'allow_blank': True}
        }

    def validate_uid(self, uid):
        """Проверяет, что UID передан и не пустой"""
        if not uid:
            raise serializers.ValidationError("UID не может быть пустым")
        return uid

    def validate_value(self, value):
        """Проверяет, что переданное значение - это число"""
        if not isinstance(value, int):
            raise serializers.ValidationError("Ожидается число")
        return value

    def validate_latitude(self, latitude):
        """Проверяет, что широта - это float число в в диапазоне [-90.0, 90.0]"""
        try:
            float(latitude)
            if not (-90.0 <= latitude <= 90.0):
                raise serializers.ValidationError("Широта должна находиться в диапазоне [-90.0, 90.0] градусов.")
            return latitude
        except (ValueError, TypeError):
            raise serializers.ValidationError("Широта должна быть числом")

    def validate_longitude(self, longitude):
        """Проверяет, что долгота - это float число в в диапазоне [-180.0, 180.0]"""
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
        return CollectibleItem.objects.create(**validated_data)


class CoachDetailSerializer(RunnerSerializer):
    athletes = serializers.SerializerMethodField()

    class Meta(RunnerSerializer.Meta):
        fields = RunnerSerializer.Meta.fields + ['athletes']

    def get_athletes(self, coach):
        """Возвращает список ID атлетов, подписанных на тренера"""
        return list(coach.coach_subscribers.filter(athlete__is_staff=False).values_list('athlete_id', flat=True))


class AthleteDetailSerializer(RunnerSerializer):
    coach = serializers.SerializerMethodField()

    class Meta(RunnerSerializer.Meta):
        fields = RunnerSerializer.Meta.fields + ['coach']

    def get_coach(self, athlete):
        """Возвращает ID первого тренера, на которого подписан атлет"""
        subscription = athlete.athlete_subscriptions.filter(is_active=True, coach__is_staff=True).first()
        return subscription.coach_id if subscription else None


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ['coach', 'athlete', 'rating']







