from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from app_run.views import company_details, RunViewSet, RunnerViewSet

router = DefaultRouter()
router.register('api/runs', RunViewSet)
router.register('api/runs/<int:run_id>/start', RunViewSet)
router.register('api/runs/<int:run_id>/stop', RunViewSet)
router.register('api/users', RunnerViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/company_details/', company_details),
    path('', include(router.urls)),
]