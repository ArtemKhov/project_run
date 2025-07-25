from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from app_run.views import company_details, RunViewSet, RunnerViewSet, StartRunAPIView, StopRunAPIView, \
    AthleteInfoAPIView, ChallengeAPIView, PositionViewSet

router = DefaultRouter()
router.register('api/runs', RunViewSet)
router.register('api/users', RunnerViewSet)
router.register('api/positions', PositionViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/company_details/', company_details),
    path('api/challenges/', ChallengeAPIView.as_view()),
    path('api/runs/<int:run_id>/start/', StartRunAPIView.as_view()),
    path('api/runs/<int:run_id>/stop/', StopRunAPIView.as_view()),
    path('api/athlete_info/<int:user_id>/', AthleteInfoAPIView.as_view()),
    path('', include(router.urls)),
]