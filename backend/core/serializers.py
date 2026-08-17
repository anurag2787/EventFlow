from rest_framework import serializers

from .models import Activity, Organization, Repository, User


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
        fields = ["id", "organization", "name", "external_id", "provider", "created_at"]
        read_only_fields = ["id", "created_at"]


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
