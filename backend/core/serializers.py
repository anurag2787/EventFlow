from rest_framework import serializers

from .models import Activity, Event, EventProcessingAttempt, Organization, Repository, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]
        read_only_fields = ["id"]


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


class RepositorySerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = Repository
        fields = [
            "id",
            "organization",
            "name",
            "external_id",
            "provider",
            "last_synced_at",
            "last_sync_status",
            "last_sync_error",
            "created_at",
        ]
        read_only_fields = ["id", "last_synced_at", "last_sync_status", "last_sync_error", "created_at"]



class ActivitySerializer(serializers.ModelSerializer):
    repository = RepositorySerializer(read_only=True)
    actor = UserSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = [
            "id",
            "repository",
            "actor",
            "activity_type",
            "target_id",
            "source_provider",
            "source_event_id",
            "source_event_type",
            "source_url",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class EventProcessingAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventProcessingAttempt
        fields = ["id", "attempt_number", "status", "error", "started_at", "completed_at"]
        read_only_fields = ["id", "started_at", "completed_at"]


class EventSerializer(serializers.ModelSerializer):
    attempts = EventProcessingAttemptSerializer(many=True, read_only=True)
    repository = RepositorySerializer(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "repository",
            "provider",
            "event_id",
            "event_type",
            "payload",
            "status",
            "retry_count",
            "max_retries",
            "next_retry_at",
            "last_error",
            "created_at",
            "updated_at",
            "attempts",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

