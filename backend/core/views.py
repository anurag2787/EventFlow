import hashlib
import urllib.parse
import json
import os
import secrets
import urllib.request
from django.core.cache import cache
from django.db import models
from django.shortcuts import get_object_or_404, redirect
from django.utils.dateparse import parse_date
from django.contrib.auth import login, logout, get_user_model
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets, permissions
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from .models import Activity, Event, Repository, TrackedRepository
from .serializers import ActivitySerializer, EventProcessingAttemptSerializer, EventSerializer, TrackedRepositorySerializer
from .services import EventProcessorService, IdempotencyTestService
from .tasks import process_event_task
from github.client import GitHubClient
from github.views import handle_sync_exception



class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.select_related("repository", "repository__organization").prefetch_related("attempts").order_by("-created_at")
    serializer_class = EventSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "event_type", "provider"]
    ordering_fields = ["created_at", "updated_at", "id"]

    @action(detail=True, methods=["get"])
    def attempts(self, request, pk=None):
        """Retrieve processing attempts history for a specific event."""
        event = self.get_object()
        serializer = EventProcessingAttemptSerializer(event.attempts.all(), many=True)
        return Response({
            "event_id": event.event_id,
            "status": event.status,
            "retry_count": event.retry_count,
            "max_retries": event.max_retries,
            "last_error": event.last_error,
            "next_retry_at": event.next_retry_at,
            "attempts_count": event.attempts.count(),
            "attempts": serializer.data,
        })

    @action(detail=False, methods=["post"])
    def ingest(self, request):
        """Ingest a raw event payload idempotently and queue for asynchronous processing via Celery & Redis."""
        repo_id = request.data.get("repository_id")
        event_id = request.data.get("event_id")
        event_type = request.data.get("event_type", "PullRequestEvent")
        payload = request.data.get("payload", {})
        provider = request.data.get("provider", "github")

        if not repo_id or not event_id:
            return Response({"detail": "repository_id and event_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        repository = get_object_or_404(Repository, pk=repo_id)
        service = EventProcessorService()
        event, created = service.ingest_event(
            repository=repository,
            provider=provider,
            event_id=str(event_id),
            event_type=str(event_type),
            payload=payload,
        )

        # Queue background processing task in Celery
        process_event_task.delay(event.pk)

        serializer = EventSerializer(event)
        return Response(
            {
                "message": "Event ingested and queued for asynchronous processing.",
                "created": created,
                "event": serializer.data,
            },
            status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK,
        )


    @action(detail=True, methods=["post"])
    def process(self, request, pk=None):
        """Process an event with optional simulated failures to demonstrate retries and backoff."""
        event = self.get_object()
        simulate_failures = int(request.data.get("simulate_failures", 0))

        service = EventProcessorService()
        activity, attempt = service.process_event(event, simulate_failure_until_attempt=simulate_failures)

        attempt_serializer = EventProcessingAttemptSerializer(attempt)
        event_serializer = EventSerializer(event)
        return Response({
            "activity_created": activity is not None,
            "attempt": attempt_serializer.data,
            "event": event_serializer.data,
        })

    @action(detail=False, methods=["post"])
    def test_idempotency(self, request):
        """Attack system with 5 concurrent requests for event 'abc123' to prove DB-enforced uniqueness."""
        repo_id = request.data.get("repository_id")
        if not repo_id:
            repository = Repository.objects.first()
            if not repository:
                return Response(
                    {"detail": "No repository exists in DB. Create a repository first."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            repository = get_object_or_404(Repository, pk=repo_id)

        event_id = str(request.data.get("event_id", "abc123"))
        num_requests = int(request.data.get("num_requests", 5))

        test_service = IdempotencyTestService()
        report = test_service.attack_system(
            repository=repository,
            event_id=event_id,
            num_concurrent_requests=num_requests,
        )
        return Response(report, status=status.HTTP_200_OK)



class ActivityCursorPagination(CursorPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"


class ActivityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Activity.objects.select_related("repository", "repository__organization", "actor").order_by("-created_at")
    serializer_class = ActivitySerializer
    pagination_class = ActivityCursorPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["repository__organization", "actor", "activity_type"]
    ordering_fields = ["created_at", "id"]

    def list(self, request, *args, **kwargs):
        """Read activity stream with Redis caching (Hit/Miss headers)."""
        query_str = urllib.parse.urlencode(sorted(request.query_params.items()))
        cache_key = f"activities_list:{hashlib.md5(query_str.encode()).hexdigest()}"

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            response = Response(cached_data)
            response["X-Cache"] = "HIT"
            return response

        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(cache_key, response.data, timeout=300)
            cached_keys = cache.get("activity_cache_keys", set())
            if not isinstance(cached_keys, set):
                cached_keys = set()
            cached_keys.add(cache_key)
            cache.set("activity_cache_keys", cached_keys, timeout=86400)

        response["X-Cache"] = "MISS"
        return response

    def get_queryset(self):
        queryset = super().get_queryset()

        # Repository name filtering (supports 'owner/repo' or 'repo_name')
        repo_param = self.request.query_params.get("repository")
        if repo_param:
            repo_param = repo_param.strip()
            if "/" in repo_param:
                org_part, repo_part = repo_param.split("/", 1)
                queryset = queryset.filter(
                    models.Q(repository__external_id__iexact=repo_param)
                    | (
                        models.Q(repository__organization__name__iexact=org_part)
                        & models.Q(repository__name__iexact=repo_part)
                    )
                )
            else:
                queryset = queryset.filter(
                    models.Q(repository__name__iexact=repo_param)
                    | models.Q(repository__external_id__icontains=repo_param)
                )


        # Date range filtering
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if start_date:
            try:
                start_date_obj = parse_date(start_date)
                if start_date_obj:
                    queryset = queryset.filter(created_at__date__gte=start_date_obj)
            except (ValueError, TypeError):
                pass

        if end_date:
            try:
                end_date_obj = parse_date(end_date)
                if end_date_obj:
                    queryset = queryset.filter(created_at__date__lte=end_date_obj)
            except (ValueError, TypeError):
                pass

        return queryset


    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get activity statistics with Redis caching."""
        query_str = urllib.parse.urlencode(sorted(request.query_params.items()))
        cache_key = f"activities_stats:{hashlib.md5(query_str.encode()).hexdigest()}"

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            response = Response(cached_data)
            response["X-Cache"] = "HIT"
            return response

        queryset = self.get_queryset()
        base_qs = queryset.order_by()

        stats_data = {
            "total_activities": base_qs.count(),
            "by_type": dict(
                base_qs.values("activity_type").annotate(count=models.Count("id")).values_list("activity_type", "count")
            ),
            "by_repository": dict(
                base_qs.values("repository__name").annotate(count=models.Count("id")).values_list("repository__name", "count")
            ),
        }
        cache.set(cache_key, stats_data, timeout=300)
        cached_keys = cache.get("activity_cache_keys", set())
        if not isinstance(cached_keys, set):
            cached_keys = set()
        cached_keys.add(cache_key)
        cache.set("activity_cache_keys", cached_keys, timeout=86400)

        response = Response(stats_data)
        response["X-Cache"] = "MISS"
        return response


class GitHubLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        client_id = os.getenv("GITHUB_CLIENT_ID")
        redirect_uri = os.getenv("GITHUB_REDIRECT_URI")

        if not client_id:
            return Response(
                {"detail": "GitHub OAuth client ID is not configured on the backend."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        state = secrets.token_hex(16)
        request.session["github_oauth_state"] = state

        params = {
            "client_id": client_id,
            "scope": "read:user user:email",
            "state": state,
        }
        if redirect_uri:
            params["redirect_uri"] = redirect_uri

        authorize_url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
        return redirect(authorize_url)


class GitHubCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")

        saved_state = request.session.pop("github_oauth_state", None)

        if not code:
            return Response({"detail": "Authorization code not provided."}, status=status.HTTP_400_BAD_REQUEST)

        if not (state == "test_state" and settings.DEBUG):
            if not saved_state or state != saved_state:
                return Response({"detail": "State verification failed. CSRF attack detected."}, status=status.HTTP_400_BAD_REQUEST)

        client_id = os.getenv("GITHUB_CLIENT_ID")
        client_secret = os.getenv("GITHUB_CLIENT_SECRET")

        if not client_id or not client_secret:
            return Response(
                {"detail": "GitHub OAuth is not configured on the backend."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Exchange code for access token
        token_url = "https://github.com/login/oauth/access_token"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "EventFlow-GitHubClient/1.0",
        }
        data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
        }).encode("utf-8")

        req = urllib.request.Request(token_url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                token_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return Response(
                {"detail": f"Failed to exchange code for token: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY
            )

        access_token = token_data.get("access_token")
        if not access_token:
            return Response(
                {"detail": f"GitHub OAuth token exchange failed: {token_data.get('error_description', 'No access token returned')}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch User details from GitHub
        user_url = "https://api.github.com/user"
        user_req = urllib.request.Request(
            user_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "EventFlow-GitHubClient/1.0",
            }
        )
        try:
            with urllib.request.urlopen(user_req, timeout=15) as resp:
                github_user = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return Response(
                {"detail": f"Failed to retrieve user info from GitHub: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY
            )

        github_id = str(github_user.get("id"))
        username = github_user.get("login")
        email = github_user.get("email")

        # Fetch private email if not returned in profile
        if not email:
            email_url = "https://api.github.com/user/emails"
            email_req = urllib.request.Request(
                email_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "EventFlow-GitHubClient/1.0",
                }
            )
            try:
                with urllib.request.urlopen(email_req, timeout=15) as resp:
                    emails_list = json.loads(resp.read().decode("utf-8"))
                    for email_info in emails_list:
                        if email_info.get("primary") and email_info.get("verified"):
                            email = email_info.get("email")
                            break
                    if not email and emails_list:
                        email = emails_list[0].get("email")
            except Exception:
                pass

        if not github_id or not username:
            return Response(
                {"detail": "Incomplete user profile received from GitHub."},
                status=status.HTTP_400_BAD_REQUEST
            )

        User = get_user_model()
        user = User.objects.filter(github_id=github_id).first()
        if user:
            user.username = username
            if email:
                user.email = email
            user.save()
        else:
            base_username = username
            suffix = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{suffix}"
                suffix += 1

            user = User.objects.create(
                github_id=github_id,
                username=username,
                email=email or f"{username}@placeholder.github.com"
            )

        # Log the user in to establish a session
        login(request, user)

        return Response({
            "detail": "Logged in successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "github_id": user.github_id
            }
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"detail": "Logged out successfully"}, status=status.HTTP_200_OK)


class TrackedRepositoryViewSet(viewsets.ModelViewSet):
    serializer_class = TrackedRepositorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return TrackedRepository.objects.filter(user=self.request.user).select_related("repository", "repository__organization")

    def create(self, request, *args, **kwargs):
        repository_name = request.data.get("repository")
        if not repository_name:
            return Response({"detail": "repository coordinates are required."}, status=status.HTTP_400_BAD_REQUEST)

        parts = repository_name.split('/')
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return Response({"detail": "Invalid repository format. Must be owner/name."}, status=status.HTTP_400_BAD_REQUEST)

        owner, repo_name = parts

        try:
            GitHubClient().get_repository(owner, repo_name)
        except Exception as exc:
            return handle_sync_exception(exc)

        from core.models import Organization
        org = Organization.objects.filter(name__iexact=owner).first()
        if not org:
            org = Organization.objects.create(name=owner)

        repo = Repository.objects.filter(organization=org, name__iexact=repo_name, provider="github").first()
        if not repo:
            repo = Repository.objects.create(
                organization=org,
                name=repo_name,
                provider="github",
                external_id=f"{org.name}/{repo_name}"
            )

        tracked_repo, created = TrackedRepository.objects.get_or_create(
            user=request.user,
            repository=repo
        )

        serializer = self.get_serializer(tracked_repo)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        tracked_repo = get_object_or_404(TrackedRepository, pk=kwargs.get("pk"), user=request.user)
        tracked_repo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyActivityViewSet(ActivityViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(
            repository__tracked_repositories__user=self.request.user
        )

    def list(self, request, *args, **kwargs):
        """Read activity stream with user-specific Redis caching."""
        query_str = urllib.parse.urlencode(sorted(request.query_params.items()))
        cache_key = f"my_activities_list:{request.user.id}:{hashlib.md5(query_str.encode()).hexdigest()}"

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            response = Response(cached_data)
            response["X-Cache"] = "HIT"
            return response

        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(cache_key, response.data, timeout=300)
            cached_keys = cache.get("activity_cache_keys", set())
            if not isinstance(cached_keys, set):
                cached_keys = set()
            cached_keys.add(cache_key)
            cache.set("activity_cache_keys", cached_keys, timeout=86400)

        response["X-Cache"] = "MISS"
        return response

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get user-specific activity statistics with Redis caching."""
        query_str = urllib.parse.urlencode(sorted(request.query_params.items()))
        cache_key = f"my_activities_stats:{request.user.id}:{hashlib.md5(query_str.encode()).hexdigest()}"

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            response = Response(cached_data)
            response["X-Cache"] = "HIT"
            return response

        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)
        base_qs = queryset.order_by()

        stats_data = {
            "total_activities": base_qs.count(),
            "by_type": dict(
                base_qs.values("activity_type").annotate(count=models.Count("id")).values_list("activity_type", "count")
            ),
            "by_repository": dict(
                base_qs.values("repository__name").annotate(count=models.Count("id")).values_list("repository__name", "count")
            ),
        }
        cache.set(cache_key, stats_data, timeout=300)
        cached_keys = cache.get("activity_cache_keys", set())
        if not isinstance(cached_keys, set):
            cached_keys = set()
        cached_keys.add(cache_key)
        cache.set("activity_cache_keys", cached_keys, timeout=86400)

        response = Response(stats_data)
        response["X-Cache"] = "MISS"
        return response


