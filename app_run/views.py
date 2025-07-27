from io import BytesIO

import openpyxl
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from geopy.distance import geodesic
from rest_framework.decorators import api_view
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.views import APIView

from .models import Run, AthleteInfo, Challenge, Position, CollectibleItem
from .serializers import RunSerializer, RunnerSerializer, AthleteInfoSerializer, ChallengeSerializer, \
    PositionSerializer, CollectibleItemSerializer


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
                raw_url = row[5] if len(row) > 5 else None
                cleaned_url = raw_url.strip().rstrip(';') if raw_url else None

                item_data = {
                    'name': row[0],
                    'uid': str(row[1]) if row[1] is not None else None,
                    'value': row[2],
                    'latitude': row[3],
                    'longitude': row[4],
                    'picture': cleaned_url
                }
            except IndexError:
                invalid_rows.append(list(row))
                continue

            serializer = CollectibleItemSerializer(data=item_data)

            if serializer.is_valid():
                valid_items.append(serializer)
            else:
                invalid_rows.append(list(row))

        created_items = []
        for serializer in valid_items:
            item_instance = serializer.save()
            created_items.append(item_instance)

        response_data = {
            "message": f"Файл обработан",
            "created_count": len(created_items),
            "invalid_rows": invalid_rows
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

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

        positions = run.position.all().order_by('id')

        total_distance = 0.0
        prev_point = None
        for position in positions:
            current_point = (float(position.latitude), float(position.longitude))
            if prev_point:
                segment_distance = geodesic(prev_point, current_point).kilometers
                total_distance += segment_distance
            prev_point = current_point

        run.status = Run.Status.FINISHED
        run.distance = round(total_distance, 3)
        run.save()

        finished_runs_count = Run.objects.filter(athlete=run.athlete,status=Run.Status.FINISHED).count()
        if finished_runs_count >= 10:
            Challenge.objects.get_or_create(
                full_name="Сделай 10 Забегов!",
                athlete=run.athlete,
                defaults={'full_name': "Сделай 10 Забегов!"}
            )

        total_km = Run.objects.filter(athlete=run.athlete,status=Run.Status.FINISHED).aggregate(total_distance=Sum('distance'))['total_distance'] or 0
        if total_km >= 50:
            Challenge.objects.get_or_create(
                full_name="Пробеги 50 километров!",
                athlete=run.athlete,
                defaults={'full_name': "Пробеги 50 километров!"}
            )

        return Response({'status': 'Забег закончен', 'distance': run.distance},
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

        return qs


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


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer

    def get_queryset(self):
        qs = self.queryset
        run = self.request.query_params.get('run')

        if run:
            qs = qs.filter(run_id=run)

        return qs


class CollectibleItemListView(ListAPIView):
    queryset = CollectibleItem.objects.all()
    serializer_class = CollectibleItemSerializer