from celery import shared_task
from django.utils import timezone
from core.models import Event
from core.services import EventProcessorService


@shared_task(bind=True, max_retries=3)
def process_event_task(self, event_pk: int, simulate_failure_until_attempt: int = 0):
    """Celery background worker task to process a raw Event asynchronously."""
    try:
        event = Event.objects.get(pk=event_pk)
    except Event.DoesNotExist:
        return {"status": "error", "message": f"Event with pk {event_pk} not found"}

    processor = EventProcessorService()
    activity, attempt = processor.process_event(
        event,
        simulate_failure_until_attempt=simulate_failure_until_attempt,
    )

    return {
        "event_pk": event.pk,
        "event_id": event.event_id,
        "event_status": event.status,
        "attempt_number": attempt.attempt_number,
        "attempt_status": attempt.status,
        "activity_created": activity is not None,
    }


@shared_task
def process_pending_retry_events_task():
    """Background task to pick up pending events whose retry backoff timer has elapsed."""
    now = timezone.now()
    pending_events = Event.objects.filter(
        status=Event.STATUS_PENDING,
        next_retry_at__lte=now,
    )[:50]

    dispatched_count = 0
    for event in pending_events:
        process_event_task.delay(event.pk)
        dispatched_count += 1

    return {"dispatched_events": dispatched_count}
