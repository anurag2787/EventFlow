from django.db import models
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from .models import Activity, Event, Repository
from .serializers import ActivitySerializer, EventProcessingAttemptSerializer, EventSerializer
from .services import EventProcessorService, IdempotencyTestService



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
        """Ingest a raw event payload idempotently."""
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

        serializer = EventSerializer(event)
        return Response(
            {"created": created, "event": serializer.data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
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

