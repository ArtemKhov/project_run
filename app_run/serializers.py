import uuid

from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Run, AthleteInfo, Challenge, Position, CollectibleItem


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'last_name', 'first_name']


class RunSerializer(serializers.ModelSerializer):
    athlete_data = UserSerializer(read_only=True, source='athlete')
    
    class Meta:
        model = Run
        fields = '__all__'


class AthleteInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AthleteInfo
        fields = ['user_id', 'goals', 'weight']


class RunnerSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    runs_finished = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'date_joined', 'username', 'last_name', 'first_name', 'type', 'runs_finished']

    def get_type(self, user):
        return "coach" if user.is_staff else "athlete"

    def get_runs_finished(self, user):
        return user.runs.filter(status='finished').count()


class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = ['full_name', 'athlete']


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ['id', 'run', 'latitude', 'longitude']

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
    uid = serializers.CharField()

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



