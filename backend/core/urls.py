from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ActivityViewSet, EventViewSet

router = DefaultRouter()
router.register(r"activities", ActivityViewSet, basename="activity")
router.register(r"events", EventViewSet, basename="event")

urlpatterns = [
    path("", include(router.urls)),
]

