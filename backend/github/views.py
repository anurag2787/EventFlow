from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

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


def error_response(detail: str, status_code: int) -> JsonResponse:
    return JsonResponse({"detail": detail}, status=status_code)


@csrf_exempt
@require_POST
def repository_sync(request, repository_id: int):
    repository = get_object_or_404(Repository, pk=repository_id)

    try:
        result = GitHubRepositorySyncService().sync_repository(repository)
    except RepositorySyncError as exc:
        return error_response(str(exc), 400)
    except GitHubAuthenticationError as exc:
        return error_response(str(exc), 401)
    except (GitHubForbiddenError, GitHubNotFoundError) as exc:
        return error_response(str(exc), exc.status_code or 400)
    except GitHubRateLimitError as exc:
        response = error_response(str(exc), 429)
        if exc.retry_after is not None:
            response["Retry-After"] = str(exc.retry_after)
        return response
    except (GitHubServerError, GitHubNetworkError, GitHubTimeoutError) as exc:
        return error_response(str(exc), 502)
    except GitHubClientError as exc:
        return error_response(str(exc), getattr(exc, "status_code", None) or 400)

    return JsonResponse(result, status=200)


@csrf_exempt
@require_POST
def sync_all_repositories(request):
    try:
        result = GitHubRepositorySyncService().sync_all_repositories()
    except RepositorySyncError as exc:
        return error_response(str(exc), 400)
    except GitHubAuthenticationError as exc:
        return error_response(str(exc), 401)
    except (GitHubForbiddenError, GitHubNotFoundError) as exc:
        return error_response(str(exc), exc.status_code or 400)
    except GitHubRateLimitError as exc:
        response = error_response(str(exc), 429)
        if exc.retry_after is not None:
            response["Retry-After"] = str(exc.retry_after)
        return response
    except (GitHubServerError, GitHubNetworkError, GitHubTimeoutError) as exc:
        return error_response(str(exc), 502)
    except GitHubClientError as exc:
        return error_response(str(exc), getattr(exc, "status_code", None) or 400)

    return JsonResponse(result, status=200)
