from django.utils.dateparse import parse_date
from django.db import models
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination

from django_filters.rest_framework import DjangoFilterBackend

from .models import Activity
from .serializers import ActivitySerializer


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
        """Get activity statistics"""
        queryset = self.get_queryset()
        base_qs = queryset.order_by()

        stats = {
            "total_activities": base_qs.count(),
            "by_type": dict(
                base_qs.values("activity_type").annotate(count=models.Count("id")).values_list("activity_type", "count")
            ),
            "by_repository": dict(
                base_qs.values("repository__name").annotate(count=models.Count("id")).values_list("repository__name", "count")
            ),
        }
        return Response(stats)

