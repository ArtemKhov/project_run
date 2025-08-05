from io import BytesIO

import openpyxl
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from geopy.distance import geodesic
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AthleteInfo, Challenge, CollectibleItem, Position, Rating, Run, Subscription
from .serializers import (
    AthleteDetailSerializer, AthleteInfoSerializer, ChallengeSerializer,
    CoachDetailSerializer, CollectibleItemSerializer, PositionSerializer,
    RunSerializer, RunnerSerializer, UserChallengeSerializer
)
from .services import (
    ChallengeAssigner, calculate_position_distance, calculate_position_speed,
    check_and_collect_items
)


@api_view(['GET'])
def company_details(request):
    """
    Получение информации о компании.
    
    Возвращает название компании, слоган и контактную информацию
    из настроек Django.
    """
    details = {
        'company_name': settings.COMPANY_NAME,
        'slogan': settings.SLOGAN,
        'contacts': settings.CONTACTS,
    }
    return Response(details)


@api_view(['POST'])
def upload_file_view(request):
    """
    Загрузка и обработка Excel файла с коллекционными предметами.
    
    Принимает Excel файл (.xlsx) с данными о коллекционных предметах
    и создает записи в базе данных. Возвращает список невалидных строк.
    """
    file = request.FILES.get('file')
    if not file:
        return Response({"error": "Файл не был передан"}, status=status.HTTP_400_BAD_REQUEST)

    if not file.name.endswith('.xlsx'):
        return Response({"error": "Файл должен быть в формате Excel (.xlsx)."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        excel_file = BytesIO(file.read())
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        worksheet = wb.active

        valid_items = []
        invalid_rows = []

        # Обработка каждой строки Excel файла
        for row_num, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
            if not any(cell is not None for cell in row):
                continue

            try:
                row_list = list(row)
                # Убираем точку с запятой из поля picture если она есть
                if len(row_list) > 5 and isinstance(row_list[5], str):
                    row_list[5] = row_list[5].rstrip(';')

                item_data = {
                    'name': row[0],
                    'uid': str(row_list[1]) if row_list[1] is not None else None,
                    'value': row[2],
                    'latitude': row[3],
                    'longitude': row[4],
                    'picture': row_list[5] if len(row_list) > 5 else None
                }
            except IndexError:
                invalid_rows.append(list(row))
                continue

            serializer = CollectibleItemSerializer(data=item_data)

            if serializer.is_valid():
                valid_items.append(serializer)
            else:
                invalid_rows.append(list(row))

        # Сохранение валидных записей
        for serializer in valid_items:
            try:
                serializer.save()
            except Exception:
                invalid_rows.append(serializer.initial_data)

        return Response(invalid_rows, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": f"Произошла ошибка во время обработки файла: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RunsPagination(PageNumberPagination):
    """Пагинация для списка забегов."""
    page_size_query_param = 'size'
    max_page_size = 50


class RunnersPagination(PageNumberPagination):
    """Пагинация для списка бегунов."""
    page_size_query_param = 'size'
    max_page_size = 50


class RunViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления забегами.
    
    Предоставляет CRUD операции для забегов с фильтрацией по статусу и атлету,
    а также сортировкой по дате создания.
    """
    queryset = Run.objects.select_related('athlete').all()
    serializer_class = RunSerializer
    pagination_class = RunsPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'athlete']
    ordering_fields = ['created_at']


class StartRunAPIView(APIView):
    """
    API для начала забега.
    
    Изменяет статус забега на 'в процессе' если он еще не начат.
    """
    
    def post(self, request, run_id):
        run = get_object_or_404(Run, id=run_id)

        if run.status == Run.Status.IN_PROGRESS:
            return Response({'error': 'Забег уже начат'}, status=status.HTTP_400_BAD_REQUEST)

        if run.status == Run.Status.FINISHED:
            return Response({'error': 'Забег уже был завершен'}, status=status.HTTP_400_BAD_REQUEST)

        run.status = Run.Status.IN_PROGRESS
        run.save()
        return Response({'status': 'Забег начат'}, status=status.HTTP_200_OK)


class StopRunAPIView(APIView):
    """
    API для завершения забега.
    
    Завершает забег, рассчитывает метрики (дистанция, время, скорость)
    и назначает челленджи атлету.
    """
    
    def post(self, request, run_id):
        run = get_object_or_404(Run, id=run_id)

        if run.status == Run.Status.FINISHED:
            return Response(
                {'error': 'Забег уже завершен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if run.status == Run.Status.INIT:
            return Response(
                {'error': 'Нельзя завершить не начатый забег'},
                status=status.HTTP_400_BAD_REQUEST
            )

        run.status = Run.Status.FINISHED

        # Расчет метрик забега если есть позиции
        if Position.objects.filter(run=run_id).exists():
            positions_qs = Position.objects.filter(run=run_id)
            positions_quantity = len(positions_qs)
            
            # Расчет общей дистанции
            distance = 0
            for i in range(positions_quantity - 1):
                distance += geodesic((positions_qs[i].latitude, positions_qs[i].longitude),
                                     (positions_qs[i + 1].latitude, positions_qs[i + 1].longitude)).kilometers
            run.distance = distance

            # Расчет времени забега
            positions_qs_sorted_by_date = positions_qs.order_by('date_time')
            run_time = positions_qs_sorted_by_date[positions_quantity - 1].date_time - positions_qs_sorted_by_date[0].date_time
            run.run_time_seconds = run_time.total_seconds()

            # Расчет средней скорости
            average_speed = positions_qs.aggregate(Avg('speed'))
            run.speed = round(average_speed['speed__avg'], 2)

        run.save()

        # Назначение вызовов атлету
        finished_runs_count = Run.objects.filter(athlete=run.athlete, status=Run.Status.FINISHED).count()
        total_km = Run.objects.filter(athlete=run.athlete, status=Run.Status.FINISHED).aggregate(total_distance=Sum('distance'))['total_distance'] or 0

        assigner = ChallengeAssigner(run, finished_runs_count, total_km, run.distance, run.run_time_seconds)
        assigner.assign()

        return Response({'status': 'Забег закончен',
                         'distance': run.distance,
                         'run_time_seconds': run.run_time_seconds,
                         'average_speed': run.speed},
                        status=status.HTTP_200_OK)


class RunnerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для просмотра информации о бегунах.
    
    Предоставляет информацию о пользователях с возможностью фильтрации
    по типу (атлет/тренер) и дополнительными аннотациями.
    """
    queryset = User.objects.filter(is_superuser=False)
    serializer_class = RunnerSerializer
    pagination_class = RunnersPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['first_name', 'last_name']
    ordering_fields = ['date_joined']

    def get_queryset(self):
        qs = self.queryset
        user_type = self.request.query_params.get('type', None)

        # Фильтрация по типу пользователя
        if user_type == 'coach':
            qs = qs.filter(is_staff=True)
        elif user_type == 'athlete':
            qs = qs.filter(is_staff=False)

        # Дополнительные аннотации для детального просмотра
        if self.action == 'retrieve':
            qs = qs.prefetch_related('collectible_items', 'athlete_subscriptions__coach', 'coach_subscribers')
            qs = qs.annotate(avg_rating=Avg('coach_rating__rating'))
        else:
            qs = qs.annotate(
                runs_finished=Count('runs', filter=Q(runs__status=Run.Status.FINISHED)),
                avg_rating=Avg('coach_rating__rating')
            )

        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return RunnerSerializer
        if self.action == 'retrieve':
            user_id = self.kwargs.get('pk')
            try:
                user = User.objects.get(id=user_id)
                if user.is_staff:
                    return CoachDetailSerializer
                else:
                    return AthleteDetailSerializer
            except User.DoesNotExist:
                return RunnerSerializer
        return super().get_serializer_class()


class AthleteInfoAPIView(APIView):
    """
    API для управления информацией об атлетах.
    
    Позволяет получать и обновлять дополнительную информацию
    об атлетах (цели, вес).
    """
    
    def get(self, request, user_id):
        """Получение информации об атлете."""
        user = get_object_or_404(User, pk=user_id)
        athlete_info, created = AthleteInfo.objects.select_related('user').get_or_create(
            user=user,
            defaults={
                'goals': '',
                'weight': None,
            }
        )
        serializer = AthleteInfoSerializer(athlete_info)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, user_id):
        """Обновление информации об атлете."""
        user = get_object_or_404(User, pk=user_id)
        weight = request.data.get('weight')
        goals = request.data.get('goals', '')
        
        # Валидация веса
        if weight is not None:
            try:
                weight = int(weight)
                if not (0 < weight < 900):
                    return Response({'error': 'Вес должен быть в пределах от 0 до 900'},
                                    status=status.HTTP_400_BAD_REQUEST)
            except (TypeError, ValueError):
                return Response({'error': 'Вес должен быть целым числом от 0 до 900 кг.'},
                                status=status.HTTP_400_BAD_REQUEST)

        athlete_info, created = AthleteInfo.objects.select_related('user').update_or_create(
            user=user,
            defaults={
                'goals': goals,
                'weight': weight,
            }
        )
        serializer = AthleteInfoSerializer(athlete_info)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChallengeAPIView(ListAPIView):
    """
    API для получения списка вызовов.
    
    Поддерживает фильтрацию по атлету через query параметр.
    """
    serializer_class = ChallengeSerializer

    def get_queryset(self):
        queryset = Challenge.objects.all().select_related('athlete')
        athlete_id = self.request.query_params.get('athlete')

        if athlete_id:
            queryset = queryset.filter(athlete__id=athlete_id)

        return queryset


class ChallengeSummaryAPIView(APIView):
    """
    API для получения сводки по челленджам.
    
    Группирует челленджи по названию и возвращает список атлетов
    для каждого челленджа.
    """
    
    def get(self, request):
        challenges = Challenge.objects.select_related('athlete').all()

        # Группировка челленджа по названию
        challenge_map = {}
        for ch in challenges:
            name = ch.full_name
            if name not in challenge_map:
                challenge_map[name] = []
            challenge_map[name].append(ch.athlete)

        # Формирование результата
        result = []
        for name, athletes in challenge_map.items():
            athletes_data = UserChallengeSerializer(athletes, many=True).data
            result.append({
                "name_to_display": name,
                "athletes": athletes_data
            })
        return Response(result)


class PositionViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления GPS позициями.
    
    Предоставляет CRUD операции для позиций с автоматическим
    расчетом дистанции и скорости при создании.
    """
    queryset = Position.objects.all()
    serializer_class = PositionSerializer

    def get_queryset(self):
        qs = self.queryset
        run = self.request.query_params.get('run')

        if run:
            qs = qs.filter(run_id=run)

        return qs

    def create(self, request, *args, **kwargs):
        """Создание новой позиции с автоматическими расчетами."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        position = serializer.save()

        # Проверка и сбор коллекционных предметов
        athlete = position.run.athlete
        check_and_collect_items(position, athlete)

        # Автоматический расчет дистанции и скорости
        calculate_position_distance(position)
        calculate_position_speed(position)
        position.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class CollectibleItemListView(ListAPIView):
    """
    API для получения списка коллекционных предметов.
    
    Возвращает все доступные коллекционные предметы.
    """
    queryset = CollectibleItem.objects.all()
    serializer_class = CollectibleItemSerializer


class SubscribeToCoachAPIView(APIView):
    """
    API для подписки атлета на тренера.
    
    Позволяет атлетам подписываться на тренеров для получения
    рекомендаций и аналитики.
    """
    
    def post(self, request, id):
        # Проверка существования тренера
        try:
            coach = User.objects.get(id=id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Тренер не найден'}, status=status.HTTP_404_NOT_FOUND)

        # Проверка что пользователь является тренером
        if not coach.is_staff:
            return Response(
                {'error': 'Можно подписываться только на тренеров'}, status=status.HTTP_400_BAD_REQUEST)

        # Получение ID атлета из запроса
        athlete_id = request.data.get('athlete')
        if not athlete_id:
            return Response(
                {'error': 'ID атлета обязателен'}, status=status.HTTP_400_BAD_REQUEST)

        # Проверка существования атлета
        try:
            athlete = User.objects.get(id=athlete_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Атлет не найден'}, status=status.HTTP_400_BAD_REQUEST)

        # Проверка что пользователь является атлетом
        if athlete.is_staff:
            return Response({'error': 'Подписываться могут только атлеты'}, status=status.HTTP_400_BAD_REQUEST)

        # Проверка существования подписки
        if Subscription.objects.filter(athlete=athlete, coach=coach).exists():
            return Response({'error': 'Подписка уже существует'}, status=status.HTTP_400_BAD_REQUEST)

        # Создание подписки
        Subscription.objects.create(athlete=athlete, coach=coach)
        
        return Response(
            {'message': f'Атлет {athlete.username} успешно подписался на тренера {coach.username}'}, 
            status=status.HTTP_200_OK
        )


class RatingCoachAPIView(APIView):
    """
    API для оценки тренеров атлетами.
    
    Позволяет атлетам оценивать тренеров по шкале от 1 до 5
    при условии активной подписки на тренера.
    """
    
    def post(self, request, coach_id):
        athlete_id = request.data.get('athlete')
        rating_value = request.data.get('rating')

        # Проверка существования тренера
        try:
            coach = User.objects.get(id=coach_id, is_staff=True)
        except User.DoesNotExist:
            return Response({'error': 'Тренер не найден'}, status=status.HTTP_404_NOT_FOUND)

        # Проверка существования атлета
        try:
            athlete = User.objects.get(id=athlete_id, is_staff=False)
        except User.DoesNotExist:
            return Response({'error': 'Атлет не найден'}, status=status.HTTP_400_BAD_REQUEST)

        # Проверка активной подписки
        if not Subscription.objects.filter(athlete=athlete, coach=coach, is_active=True).exists():
            return Response({'error': 'Атлет должен быть подписан на тренера, чтобы оценить его'}, status=status.HTTP_400_BAD_REQUEST)

        # Валидация оценки
        try:
            rating_int = int(rating_value)
        except (TypeError, ValueError):
            return Response({'error': 'Оценка должна быть целым числом от 1 до 5'}, status=status.HTTP_400_BAD_REQUEST)
        if rating_int < 1 or rating_int > 5:
            return Response({'error': 'Оценка должна быть от 1 до 5'}, status=status.HTTP_400_BAD_REQUEST)

        # Создание или обновление оценки
        obj, created = Rating.objects.update_or_create(
            athlete=athlete,
            coach=coach,
            defaults={'rating': rating_int}
        )

        return Response({'message': f'Атлет {athlete.username} успешно оценил тренера {coach.username} на {rating_int}'}, status=status.HTTP_200_OK)


class AnalyticsForCoachAPIView(APIView):
    """
    API для получения аналитики тренера по подписанным атлетам.
    
    Возвращает статистику по забегам подписанных атлетов:
    - Самый длинный забег
    - Общая дистанция по атлетам
    - Средняя скорость
    """
    
    def get(self, request, coach_id):
        # Проверка существования тренера
        try:
            coach = User.objects.get(id=coach_id, is_staff=True)
        except User.DoesNotExist:
            return Response({'error': 'Тренер не найден'}, status=status.HTTP_404_NOT_FOUND)

        # Получение подписанных атлетов
        subscribed_athletes = Subscription.objects.filter(coach_id=coach_id, is_active=True).values_list('athlete_id', flat=True)

        if not subscribed_athletes:
            return Response({
                'longest_run_user': None,
                'longest_run_value': None,
                'total_run_user': None,
                'total_run_value': None,
                'speed_avg_user': None,
                'speed_avg_value': None
            }, status=status.HTTP_200_OK)

        finished_runs = Run.objects.filter(athlete_id__in=subscribed_athletes, status=Run.Status.FINISHED)

        # Поиск самого длинного забега
        longest_run = finished_runs.order_by('-distance').first()
        longest_run_user = longest_run.athlete_id if longest_run else None
        longest_run_value = longest_run.distance if longest_run else None

        # Поиск атлета с наибольшей общей дистанцией
        total_distance_by_athlete = finished_runs.values('athlete_id').annotate(
            total_distance=Sum('distance')
        ).order_by('-total_distance').first()

        total_run_user = total_distance_by_athlete['athlete_id'] if total_distance_by_athlete else None
        total_run_value = total_distance_by_athlete['total_distance'] if total_distance_by_athlete else None

        # Поиск атлета с максимальной средней скоростью
        athletes_with_speed = User.objects.filter(
            id__in=subscribed_athletes
        ).annotate(
            avg_speed=Avg('runs__speed', filter=Q(runs__status=Run.Status.FINISHED))
        ).order_by('-avg_speed')

        speed_avg_user = None
        speed_avg_value = None

        if athletes_with_speed.exists():
            fastest_athlete = athletes_with_speed.first()
            if fastest_athlete.avg_speed is not None:
                speed_avg_user = fastest_athlete.id
                speed_avg_value = round(fastest_athlete.avg_speed, 2)

        analytics = {
            'longest_run_user': longest_run_user,
            'longest_run_value': longest_run_value,
            'total_run_user': total_run_user,
            'total_run_value': total_run_value,
            'speed_avg_user': speed_avg_user,
            'speed_avg_value': speed_avg_value
        }

        return Response(analytics, status=status.HTTP_200_OK)