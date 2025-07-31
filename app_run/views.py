from io import BytesIO

import openpyxl
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Sum, Min, Max, Count, Q, Avg
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import api_view
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.views import APIView

from .models import Run, AthleteInfo, Challenge, Position, CollectibleItem, Subscribe, Rating
from .serializers import RunSerializer, RunnerSerializer, AthleteInfoSerializer, ChallengeSerializer, \
    PositionSerializer, CollectibleItemSerializer, CoachDetailSerializer, AthleteDetailSerializer, \
    UserChallengeSerializer
from .services import check_and_collect_items, calculate_run_time_seconds, calculate_run_distance, \
    calculate_position_distance, calculate_position_speed, calculate_average_speed, ChallengeAssigner


@api_view(['GET'])
def company_details(request):
    details = {
        'company_name': settings.COMPANY_NAME,
        'slogan': settings.SLOGAN,
        'contacts': settings.CONTACTS,
    }
    return Response(details)


@api_view(['POST'])
def upload_file_view(request):
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

        for row_num, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
            if not any(cell is not None for cell in row):
                continue

            try:
                row_list = list(row)
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


        created_count = 0
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
    page_size_query_param = 'size'
    max_page_size = 50


class RunnersPagination(PageNumberPagination):
    page_size_query_param = 'size'
    max_page_size = 50


class RunViewSet(viewsets.ModelViewSet):
    queryset = Run.objects.select_related('athlete').all()
    serializer_class = RunSerializer
    pagination_class = RunsPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'athlete']
    ordering_fields = ['created_at']


class StartRunAPIView(APIView):
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

        positions = run.position.all()

        total_distance = calculate_run_distance(positions)
        run_time_seconds = calculate_run_time_seconds(positions)
        average_speed = calculate_average_speed(positions)

        run.status = Run.Status.FINISHED
        run.distance = total_distance
        run.run_time_seconds = run_time_seconds
        run.speed = average_speed

        run.save()

        finished_runs_count = Run.objects.filter(athlete=run.athlete, status=Run.Status.FINISHED).count()
        total_km = Run.objects.filter(athlete=run.athlete, status=Run.Status.FINISHED).aggregate(total_distance=Sum('distance'))['total_distance'] or 0

        assigner = ChallengeAssigner(run, finished_runs_count, total_km, total_distance, run_time_seconds)
        assigner.assign()

        return Response({'status': 'Забег закончен',
                         'distance': run.distance,
                         'run_time_seconds': run.run_time_seconds,
                         'average_speed': run.speed},
                        status=status.HTTP_200_OK)


class RunnerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(is_superuser=False)
    serializer_class = RunnerSerializer
    pagination_class = RunnersPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['first_name', 'last_name']
    ordering_fields = ['date_joined']

    def get_queryset(self):
        qs = self.queryset
        user_type = self.request.query_params.get('type', None)

        if user_type == 'coach':
            qs = qs.filter(is_staff=True)
        elif user_type == 'athlete':
            qs = qs.filter(is_staff=False)

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
    def get(self, request, user_id):
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
        user = get_object_or_404(User, pk=user_id)
        weight = request.data.get('weight')
        goals = request.data.get('goals', '')
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
    serializer_class = ChallengeSerializer

    def get_queryset(self):
        queryset = Challenge.objects.all().select_related('athlete')
        athlete_id = self.request.query_params.get('athlete')

        if athlete_id:
            queryset = queryset.filter(athlete__id=athlete_id)

        return queryset


class ChallengeSummaryAPIView(APIView):
    def get(self, request):
        challenges = Challenge.objects.select_related('athlete').all()

        challenge_map = {}
        for ch in challenges:
            name = ch.full_name
            if name not in challenge_map:
                challenge_map[name] = []
            challenge_map[name].append(ch.athlete)

        result = []
        for name, athletes in challenge_map.items():
            athletes_data = UserChallengeSerializer(athletes, many=True).data
            result.append({
                "name_to_display": name,
                "athletes": athletes_data
            })
        return Response(result)


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer

    def get_queryset(self):
        qs = self.queryset
        run = self.request.query_params.get('run')

        if run:
            qs = qs.filter(run_id=run)

        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        position = serializer.save()

        athlete = position.run.athlete
        check_and_collect_items(position, athlete)

        calculate_position_distance(position)
        calculate_position_speed(position)
        position.save()

        serializer = self.get_serializer(position)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class CollectibleItemListView(ListAPIView):
    queryset = CollectibleItem.objects.all()
    serializer_class = CollectibleItemSerializer


class SubscribeToCoachAPIView(APIView):
    def post(self, request, id):
        try:
            coach = User.objects.get(id=id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Тренер не найден'}, status=status.HTTP_404_NOT_FOUND)
        

        if not coach.is_staff:
            return Response(
                {'error': 'Можно подписываться только на тренеров'}, status=status.HTTP_400_BAD_REQUEST)
        

        athlete_id = request.data.get('athlete')
        if not athlete_id:
            return Response(
                {'error': 'ID атлета обязателен'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            athlete = User.objects.get(id=athlete_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Атлет не найден'}, status=status.HTTP_400_BAD_REQUEST)

        if athlete.is_staff:
            return Response({'error': 'Подписываться могут только атлеты'}, status=status.HTTP_400_BAD_REQUEST)

        if Subscribe.objects.filter(athlete=athlete, coach=coach).exists():
            return Response({'error': 'Подписка уже существует'}, status=status.HTTP_400_BAD_REQUEST)

        Subscribe.objects.create(athlete=athlete, coach=coach)
        
        return Response(
            {'message': f'Атлет {athlete.username} успешно подписался на тренера {coach.username}'}, 
            status=status.HTTP_200_OK
        )


class RatingCoachAPIView(APIView):
    def post(self, request, coach_id):
        athlete_id = request.data.get('athlete')
        rating_value = request.data.get('rating')


        try:
            coach = User.objects.get(id=coach_id, is_staff=True)
        except User.DoesNotExist:
            return Response({'error': 'Тренер не найден'}, status=status.HTTP_404_NOT_FOUND)

        try:
            athlete = User.objects.get(id=athlete_id, is_staff=False)
        except User.DoesNotExist:
            return Response({'error': 'Атлет не найден'}, status=status.HTTP_400_BAD_REQUEST)


        if not Subscribe.objects.filter(athlete=athlete, coach=coach, is_active=True).exists():
            return Response({'error': 'Атлет должен быть подписан на тренера, чтобы оценить его'}, status=status.HTTP_400_BAD_REQUEST)


        try:
            rating_int = int(rating_value)
        except (TypeError, ValueError):
            return Response({'error': 'Оценка должна быть целым числом от 1 до 5'}, status=status.HTTP_400_BAD_REQUEST)
        if rating_int < 1 or rating_int > 5:
            return Response({'error': 'Оценка должна быть от 1 до 5'}, status=status.HTTP_400_BAD_REQUEST)


        obj, created = Rating.objects.update_or_create(
            athlete=athlete,
            coach=coach,
            defaults={'rating': rating_int}
        )

        return Response({'message': f'Атлет {athlete.username} успешно оценил тренера {coach.username} на {rating_int}'}, status=status.HTTP_200_OK)

class AnalyticsForCoachAPIView(APIView):
    def get(self, request, coach_id):
        try:
            coach = User.objects.get(id=coach_id, is_staff=True)
        except User.DoesNotExist:
            return Response({'error': 'Тренер не найден'}, status=status.HTTP_404_NOT_FOUND)

        subscribed_athletes = Subscribe.objects.filter(coach_id=coach_id, is_active=True).values_list('athlete_id', flat=True)

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
        
        # Самый длинный забег
        longest_run = finished_runs.order_by('-distance').first()
        longest_run_user = longest_run.athlete_id if longest_run else None
        longest_run_value = longest_run.distance if longest_run else None
        
        # Общая дистанция по атлетам
        total_distance_by_athlete = finished_runs.values('athlete_id').annotate(
            total_distance=Sum('distance')
        ).order_by('-total_distance').first()
        
        total_run_user = total_distance_by_athlete['athlete_id'] if total_distance_by_athlete else None
        total_run_value = total_distance_by_athlete['total_distance'] if total_distance_by_athlete else None

        # Используем ORM для расчёта средней скорости
        athletes_with_speed = User.objects.filter(
            id__in=subscribed_athletes
        ).annotate(
            avg_speed=Avg('runs__speed', filter=Q(runs__status=Run.Status.FINISHED))
        ).order_by('-avg_speed')

        # Берём атлета с максимальной средней скоростью
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