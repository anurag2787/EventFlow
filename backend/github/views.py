from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.models import Repository

from .exceptions import (
    GitHubAuthenticationError,
    GitHubClientError,
    GitHubForbiddenError,
    GitHubNetworkError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubServerError,
    GitHubTimeoutError,
)
from .services import RepositorySyncError, GitHubRepositorySyncService


def handle_sync_exception(exc: Exception) -> Response:
    if isinstance(exc, RepositorySyncError):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, GitHubAuthenticationError):
        return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
    if isinstance(exc, (GitHubForbiddenError, GitHubNotFoundError)):
        code = getattr(exc, "status_code", None) or status.HTTP_400_BAD_REQUEST
        return Response({"detail": str(exc)}, status=code)
    if isinstance(exc, GitHubRateLimitError):
        headers = {}
        if getattr(exc, "retry_after", None) is not None:
            headers["Retry-After"] = str(exc.retry_after)
        return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS, headers=headers)
    if isinstance(exc, (GitHubServerError, GitHubNetworkError, GitHubTimeoutError)):
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    if isinstance(exc, GitHubClientError):
        code = getattr(exc, "status_code", None) or status.HTTP_400_BAD_REQUEST
        return Response({"detail": str(exc)}, status=code)

    return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def repository_sync(request, repository_id: int):
    """Synchronize GitHub events for a single repository."""
    repository = get_object_or_404(Repository, pk=repository_id)

    try:
        result = GitHubRepositorySyncService().sync_repository(repository)
    except Exception as exc:
        return handle_sync_exception(exc)

    return Response(result, status=status.HTTP_200_OK)


@api_view(["POST"])
def sync_all_repositories(request):
    """Synchronize GitHub events for all registered GitHub repositories."""
    try:
        result = GitHubRepositorySyncService().sync_all_repositories()
    except Exception as exc:
        return handle_sync_exception(exc)

    return Response(result, status=status.HTTP_200_OK)

