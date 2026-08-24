from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    github_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.username


class Organization(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Organizations'

    def __str__(self):
        return self.name


class Repository(models.Model):
    SYNC_STATUS_NEVER = 'NEVER'
    SYNC_STATUS_IN_PROGRESS = 'IN_PROGRESS'
    SYNC_STATUS_SUCCESS = 'SUCCESS'
    SYNC_STATUS_FAILED = 'FAILED'

    SYNC_STATUS_CHOICES = [
        (SYNC_STATUS_NEVER, 'Never Synced'),
        (SYNC_STATUS_IN_PROGRESS, 'In Progress'),
        (SYNC_STATUS_SUCCESS, 'Success'),
        (SYNC_STATUS_FAILED, 'Failed'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='repositories',
    )
    name = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255, blank=True, default='')
    provider = models.CharField(max_length=100)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default=SYNC_STATUS_NEVER,
    )
    last_sync_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.external_id and self.organization_id and self.name:
            self.external_id = f'{self.organization.name}/{self.name}'
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'Repositories'

    def __str__(self):
        return f'{self.organization.name}/{self.name} ({self.provider})'



class Activity(models.Model):
    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name='activities',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities',
    )
    activity_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=255)
    source_provider = models.CharField(max_length=100, default='github')
    source_event_id = models.CharField(max_length=255, null=True, blank=True)
    source_event_type = models.CharField(max_length=100, blank=True, default='')
    source_url = models.URLField(max_length=500, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Activities'
        constraints = [
            models.UniqueConstraint(
                fields=['repository', 'source_provider', 'source_event_id'],
                name='uniq_activity_source_event',
            )
        ]
        indexes = [
            models.Index(fields=['repository', '-created_at'], name='idx_activity_repo_created'),
            models.Index(fields=['actor', '-created_at'], name='idx_activity_actor_created'),
            models.Index(fields=['activity_type', '-created_at'], name='idx_activity_type_created'),
        ]

    def __str__(self):
        return f'{self.activity_type} on {self.repository.organization.name}/{self.repository.name}'


class WebhookSubscription(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='webhook_subscriptions',
    )
    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name='webhook_subscriptions',
    )
    provider = models.CharField(max_length=100)
    secret = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Webhook Subscriptions'


    def __str__(self):
        return f'{self.provider} subscription for {self.repository}'


class Event(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_PROCESSING = 'PROCESSING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_FAILED = 'FAILED'  # Dead-letter status

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed (Dead-Letter)'),
    ]

    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name='events',
    )
    provider = models.CharField(max_length=100, default='github')
    event_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Events'
        constraints = [
            models.UniqueConstraint(
                fields=['repository', 'provider', 'event_id'],
                name='uniq_event_provider_id',
            )
        ]

    def __str__(self):
        return f'Event {self.event_id} ({self.event_type}) - {self.status}'


class EventProcessingAttempt(models.Model):
    STATUS_SUCCESS = 'SUCCESS'
    STATUS_FAILED = 'FAILED'

    STATUS_CHOICES = [
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='attempts',
    )
    attempt_number = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error = models.TextField(blank=True, default='')
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField()

    class Meta:
        verbose_name_plural = 'Event Processing Attempts'
        ordering = ['attempt_number']

    def __str__(self):
        return f'Attempt {self.attempt_number} for Event {self.event.event_id} ({self.status})'


class TrackedRepository(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tracked_repositories',
    )
    repository = models.ForeignKey(
        Repository,
        on_delete=models.CASCADE,
        related_name='tracked_repositories',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'repository')
        verbose_name_plural = 'Tracked Repositories'

    def __str__(self):
        return f'{self.user.username} -> {self.repository.external_id}'

