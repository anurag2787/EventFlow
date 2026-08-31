from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import Event, Repository
from core.serializers import EventProcessingAttemptSerializer, EventSerializer
from core.services import EventProcessorService, IdempotencyTestService
from core.tasks import process_event_task


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
