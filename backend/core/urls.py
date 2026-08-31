from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ActivityViewSet,
    EventViewSet,
    GitHubLoginView,
    GitHubCallbackView,
    CurrentUserView,
    LogoutView,
    TrackedRepositoryViewSet,
    MyActivityViewSet,
)

router = DefaultRouter()
router.register(r"activities", ActivityViewSet, basename="activity")
router.register(r"events", EventViewSet, basename="event")
router.register(r"me/repositories", TrackedRepositoryViewSet, basename="me-repository")
router.register(r"me/activities", MyActivityViewSet, basename="me-activity")

urlpatterns = [
    path("auth/github/login/", GitHubLoginView.as_view(), name="github-login"),
    path("auth/github/callback/", GitHubCallbackView.as_view(), name="github-callback"),
    path("auth/me/", CurrentUserView.as_view(), name="current-user"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("", include(router.urls)),
]

