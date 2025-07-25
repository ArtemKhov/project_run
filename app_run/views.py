from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import api_view
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.views import APIView

from .models import Run, AthleteInfo, Challenge
from .serializers import RunSerializer, RunnerSerializer, AthleteInfoSerializer, ChallengeSerializer


@api_view(['GET'])
def company_details(request):
    details = {
        'company_name': settings.COMPANY_NAME,
        'slogan': settings.SLOGAN,
        'contacts': settings.CONTACTS,
    }
    return Response(details)


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

        run.status = Run.Status.FINISHED
        run.save()

        finished_runs_count = Run.objects.filter(athlete=run.athlete,status=Run.Status.FINISHED).count()

        if finished_runs_count >= 10:
            Challenge.objects.get_or_create(
                full_name="Сделай 10 Забегов!",
                athlete=run.athlete,
                defaults={'full_name': "Сделай 10 Забегов!"}
            )

        return Response({'status': 'Забег закончен'}, status=status.HTTP_200_OK)


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