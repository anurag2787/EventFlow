from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from core.models import Activity, Repository

from .client import GitHubClient
from .normalizers import GitHubEventNormalizer


class RepositorySyncError(Exception):
    pass


class UnsupportedRepositoryProviderError(RepositorySyncError):
    pass


class RepositoryReferenceError(RepositorySyncError):
    pass


@dataclass(slots=True)
class GitHubRepositorySyncService:
    client: GitHubClient | None = None
    normalizer: GitHubEventNormalizer | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = GitHubClient()
        if self.normalizer is None:
            self.normalizer = GitHubEventNormalizer()

    def sync_repository(self, repository: Repository, *, per_page: int = 100) -> dict[str, Any]:
        if repository.provider.lower() != "github":
            raise UnsupportedRepositoryProviderError("Only GitHub repositories can be synchronized")

        owner, repo_name = self.resolve_coordinates(repository)

        fetched_events = 0
        created_activities = 0
        skipped_events = 0
        page = 1

        while True:
            events = self.client.get_repository_events(owner, repo_name, per_page=per_page, page=page)
            if not isinstance(events, list):
                raise RepositorySyncError("GitHub events response must be a list")

            if not events:
                break

            fetched_events += len(events)
            event_ids = [str(event.get("id")) for event in events if event.get("id") is not None]
            existing_ids = set(
                Activity.objects.filter(
                    repository=repository,
                    source_provider="github",
                    source_event_id__in=event_ids,
                ).values_list("source_event_id", flat=True)
            )

            to_create_activities: list[Activity] = []
            for event in events:
                external_id = event.get("id")
                if external_id is None:
                    skipped_events += 1
                    continue

                external_id_str = str(external_id)
                if external_id_str in existing_ids:
                    skipped_events += 1
                    continue

                normalized_event = self.normalizer.normalize(event)
                if normalized_event is not None:
                    to_create_activities.append(
                        Activity(
                            repository=repository,
                            activity_type=normalized_event.activity_type,
                            target_id=normalized_event.target_id,
                            source_provider="github",
                            source_event_id=external_id_str,
                            source_event_type=str(event.get("type") or "unknown"),
                            source_url=normalized_event.source_url,
                            metadata=normalized_event.metadata,
                        )
                    )
                else:
                    skipped_events += 1

            if to_create_activities:
                with transaction.atomic():
                    Activity.objects.bulk_create(to_create_activities, batch_size=500)
                created_activities += len(to_create_activities)

            if len(events) < per_page:
                break
            page += 1

        return {
            "repository_id": repository.id,
            "provider": repository.provider,
            "owner": owner,
            "name": repo_name,
            "fetched_events": fetched_events,
            "created_activities": created_activities,
            "skipped_events": skipped_events,
        }

    def sync_all_repositories(self, *, per_page: int = 100) -> dict[str, Any]:
        repositories = Repository.objects.select_related("organization").filter(provider__iexact="github").order_by("id")

        results: list[dict[str, Any]] = []
        totals = {
            "repositories": 0,
            "fetched_events": 0,
            "created_activities": 0,
            "skipped_events": 0,
        }

        for repository in repositories:
            result = self.sync_repository(repository, per_page=per_page)
            results.append(result)
            totals["repositories"] += 1
            totals["fetched_events"] += result["fetched_events"]
            totals["created_activities"] += result["created_activities"]
            totals["skipped_events"] += result["skipped_events"]

        return {
            "totals": totals,
            "results": results,
        }

    def resolve_coordinates(self, repository: Repository) -> tuple[str, str]:
        if repository.external_id and "/" in repository.external_id:
            owner, repo_name = repository.external_id.split("/", 1)
            if owner and repo_name:
                return owner, repo_name

        owner = repository.organization.name.strip() if repository.organization and repository.organization.name else ""
        repo_name = repository.name.strip() if repository.name else ""

        if owner and repo_name:
            return owner, repo_name

        raise RepositoryReferenceError(
            "Unable to determine the GitHub owner and repository name for this repository"
        )