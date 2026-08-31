import hashlib
import urllib.parse

from django.core.cache import cache
from django.db import models
from django.utils.dateparse import parse_date
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from core.models import Activity
from core.serializers import ActivitySerializer


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
