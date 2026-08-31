# Aggregates all core API views — each resource has its own module.

from core.views.activities import ActivityCursorPagination, ActivityViewSet, MyActivityViewSet
from core.views.events import EventViewSet
from core.views.auth import (
    GitHubLoginView,
    GitHubCallbackView,
    LogoutView,
    TrackedRepositoryViewSet,
)

__all__ = [
    "ActivityCursorPagination",
    "ActivityViewSet",
    "MyActivityViewSet",
    "EventViewSet",
    "GitHubLoginView",
    "GitHubCallbackView",
    "LogoutView",
    "TrackedRepositoryViewSet",
]
