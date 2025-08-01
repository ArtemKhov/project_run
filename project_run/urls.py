from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken import views as drf_auth_views

from app_run.views import company_details, RunViewSet, RunnerViewSet, StartRunAPIView, StopRunAPIView, \
    AthleteInfoAPIView, ChallengeAPIView, PositionViewSet, CollectibleItemListView, upload_file_view, \
    SubscribeToCoachAPIView, ChallengeSummaryAPIView, RatingCoachAPIView, AnalyticsForCoachAPIView

router = DefaultRouter()
router.register('api/runs', RunViewSet)
router.register('api/users', RunnerViewSet)
router.register('api/positions', PositionViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/company_details/', company_details),
    path('api/upload_file/', upload_file_view),
    path('api/collectible_item/', CollectibleItemListView.as_view()),
    path('api/challenges/', ChallengeAPIView.as_view()),
    path('api/challenges_summary/', ChallengeSummaryAPIView.as_view()),
    path('api/runs/<int:run_id>/start/', StartRunAPIView.as_view()),
    path('api/runs/<int:run_id>/stop/', StopRunAPIView.as_view()),
    path('api/athlete_info/<int:user_id>/', AthleteInfoAPIView.as_view()),
    path('api/subscribe_to_coach/<int:id>/', SubscribeToCoachAPIView.as_view()),
    path('api/rate_coach/<int:coach_id>/', RatingCoachAPIView.as_view()),
    path('api/analytics_for_coach/<int:coach_id>/', AnalyticsForCoachAPIView.as_view()),
    path('api/token/', drf_auth_views.obtain_auth_token),
    path('', include(router.urls)),
]