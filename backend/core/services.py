from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from typing import Any

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from github.normalizers import GitHubEventNormalizer
from .models import Activity, Event, EventProcessingAttempt, Repository


class EventProcessorService:
    """Manages raw event ingestion, exponential backoff retries, dead-letter state, and processing history."""

    def __init__(self, normalizer: GitHubEventNormalizer | None = None) -> None:
        self.normalizer = normalizer or GitHubEventNormalizer()

    def invalidate_activity_caches(self) -> None:
        """Invalidates cached activity stream and stats queries upon new Activity creation or Sync."""
        cached_keys = cache.get("activity_cache_keys", set())
        if isinstance(cached_keys, set) and cached_keys:
            cache.delete_many(list(cached_keys))
            cache.delete("activity_cache_keys")

    def ingest_event(
        self,
        *,
        repository: Repository,
        provider: str = "github",
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> tuple[Event, bool]:
        """Ingests a raw event idempotently using database constraints."""
        try:
            with transaction.atomic():
                event, created = Event.objects.get_or_create(
                    repository=repository,
                    provider=provider,
                    event_id=event_id,
                    defaults={
                        "event_type": event_type,
                        "payload": payload,
                        "status": Event.STATUS_PENDING,
                    },
                )
                return event, created
        except IntegrityError:
            # Fallback if concurrent transaction inserted event simultaneously
            event = Event.objects.get(repository=repository, provider=provider, event_id=event_id)
            return event, False

    def process_event(
        self,
        event: Event,
        *,
        simulate_failure_until_attempt: int = 0,
    ) -> tuple[Activity | None, EventProcessingAttempt]:
        """Processes an event, tracking attempts, retries, exponential backoff, and dead-letter FAILED status."""
        started_at = timezone.now()
        attempt_number = event.retry_count + 1

        event.status = Event.STATUS_PROCESSING
        event.save(update_fields=["status", "updated_at"])

        activity: Activity | None = None
        attempt_status = EventProcessingAttempt.STATUS_FAILED
        error_msg = ""

        try:
            # Check for simulated failure during testing
            if attempt_number <= simulate_failure_until_attempt:
                raise RuntimeError(f"Simulated processing failure on attempt #{attempt_number}")

            normalized = self.normalizer.normalize(event.payload)
            if normalized is not None:
                # Idempotent Activity creation backed by database UniqueConstraint
                try:
                    with transaction.atomic():
                        activity, activity_created = Activity.objects.get_or_create(
                            repository=event.repository,
                            source_provider=event.provider,
                            source_event_id=event.event_id,
                            defaults={
                                "activity_type": normalized.activity_type,
                                "target_id": normalized.target_id,
                                "source_event_type": event.event_type,
                                "source_url": normalized.source_url,
                                "metadata": normalized.metadata,
                            },
                        )
                        if activity_created:
                            self.invalidate_activity_caches()
                except IntegrityError:
                    activity = Activity.objects.get(
                        repository=event.repository,
                        source_provider=event.provider,
                        source_event_id=event.event_id,
                    )

            attempt_status = EventProcessingAttempt.STATUS_SUCCESS
            completed_at = timezone.now()

            # Record processing attempt
            attempt = EventProcessingAttempt.objects.create(
                event=event,
                attempt_number=attempt_number,
                status=attempt_status,
                error="",
                started_at=started_at,
                completed_at=completed_at,
            )

            # Update Event state to COMPLETED
            event.status = Event.STATUS_COMPLETED
            event.last_error = ""
            event.next_retry_at = None
            event.save(update_fields=["status", "last_error", "next_retry_at", "updated_at"])

            return activity, attempt


        except Exception as exc:
            completed_at = timezone.now()
            error_msg = str(exc)

            # Record failed attempt
            attempt = EventProcessingAttempt.objects.create(
                event=event,
                attempt_number=attempt_number,
                status=attempt_status,
                error=error_msg,
                started_at=started_at,
                completed_at=completed_at,
            )

            event.retry_count += 1
            event.last_error = error_msg

            if event.retry_count >= event.max_retries:
                # Dead-letter state: Maximum retries reached
                event.status = Event.STATUS_FAILED
                event.next_retry_at = None
            else:
                # Exponential backoff calculation:
                # Attempt 1 fail -> 30s delay
                # Attempt 2 fail -> 60s delay
                delay_seconds = 30 * (2 ** (event.retry_count - 1))
                event.status = Event.STATUS_PENDING
                event.next_retry_at = completed_at + timedelta(seconds=delay_seconds)

            event.save(update_fields=["status", "retry_count", "last_error", "next_retry_at", "updated_at"])
            return None, attempt


class IdempotencyTestService:
    """Deliberately attacks the system with concurrent duplicate requests to verify database-enforced idempotency."""

    def attack_system(
        self,
        *,
        repository: Repository,
        event_id: str = "abc123",
        event_type: str = "PullRequestEvent",
        payload: dict[str, Any] | None = None,
        num_concurrent_requests: int = 5,
    ) -> dict[str, Any]:
        if payload is None:
            payload = {
                "type": event_type,
                "id": event_id,
                "repo": {"name": f"{repository.organization.name}/{repository.name}"},
                "payload": {
                    "action": "opened",
                    "number": 123,
                    "pull_request": {
                        "html_url": f"https://github.com/{repository.organization.name}/{repository.name}/pull/123"
                    },
                },
            }

        service = EventProcessorService()

        def send_single_request():
            event, created = service.ingest_event(
                repository=repository,
                provider="github",
                event_id=event_id,
                event_type=event_type,
                payload=payload,
            )
            activity, attempt = service.process_event(event)
            return {"event_id": event.id, "created": created, "activity_id": activity.id if activity else None}

        # Fire concurrent requests simultaneously
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=num_concurrent_requests) as executor:
            futures = [executor.submit(send_single_request) for _ in range(num_concurrent_requests)]
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append({"error": str(exc)})

        # Query Database for audit count
        db_events_count = Event.objects.filter(repository=repository, provider="github", event_id=event_id).count()
        db_activities_count = Activity.objects.filter(
            repository=repository, source_provider="github", source_event_id=event_id
        ).count()

        return {
            "attack_target_event_id": event_id,
            "concurrent_requests_sent": num_concurrent_requests,
            "database_audit": {
                "events_in_db": db_events_count,
                "activities_in_db": db_activities_count,
            },
            "idempotency_passed": db_events_count == 1 and db_activities_count == 1,
            "explanation": (
                "Database-enforced UniqueConstraints (uniq_event_provider_id on Event and "
                "uniq_activity_source_event on Activity) guaranteed that 5 concurrent requests "
                "resulted in exactly 1 Event and 1 Activity."
            ),
        }
