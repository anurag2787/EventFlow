from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'User'

    def __str__(self):
        return self.username


class Organization(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Organization'

    def __str__(self):
        return self.name


class Repository(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='repositories',
    )
    name = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255, blank=True, default='')
    provider = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.external_id and self.organization_id and self.name:
            self.external_id = f'{self.organization.name}/{self.name}'
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'Repository'

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
        verbose_name_plural = 'Activity'
        constraints = [
            models.UniqueConstraint(
                fields=['repository', 'source_provider', 'source_event_id'],
                name='uniq_activity_source_event',
            )
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
        verbose_name_plural = 'Webhook Subscription'

    def __str__(self):
        return f'{self.provider} subscription for {self.repository}'
