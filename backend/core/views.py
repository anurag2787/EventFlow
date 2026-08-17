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
    queryset = Activity.objects.select_related("repository", "actor").order_by("-created_at")
    serializer_class = ActivitySerializer
    pagination_class = ActivityCursorPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["repository", "repository__organization", "actor", "activity_type"]
    ordering_fields = ["created_at", "id"]

    def get_queryset(self):
        queryset = super().get_queryset()

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

        stats = {
            "total_activities": queryset.count(),
            "by_type": dict(
                queryset.values("activity_type").annotate(count=models.Count("id")).values_list("activity_type", "count")
            ),
            "by_repository": dict(
                queryset.values("repository__name").annotate(count=models.Count("id")).values_list("repository__name", "count")
            ),
        }
        return Response(stats)
