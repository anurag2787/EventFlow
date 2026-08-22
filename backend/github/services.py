from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from core.models import Activity, Repository
from core.services import EventProcessorService

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
    processor: EventProcessorService | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = GitHubClient()
        if self.normalizer is None:
            self.normalizer = GitHubEventNormalizer()
        if self.processor is None:
            self.processor = EventProcessorService(normalizer=self.normalizer)

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

            for event in events:
                external_id = event.get("id")
                if external_id is None:
                    skipped_events += 1
                    continue

                external_id_str = str(external_id)
                event_type_str = str(event.get("type") or "unknown")

                raw_event, created = self.processor.ingest_event(
                    repository=repository,
                    provider="github",
                    event_id=external_id_str,
                    event_type=event_type_str,
                    payload=event,
                )

                if not created and raw_event.status == "COMPLETED":
                    skipped_events += 1
                    continue

                activity, attempt = self.processor.process_event(raw_event)
                if activity is not None:
                    created_activities += 1
                else:
                    skipped_events += 1

            if len(events) < per_page:
                break
            page += 1

        return {
            "repository_id": repository.id,
            "provider": repository.provider,
            "owner": owner,
            "name": repo_name,
            "status": "success",
            "fetched_events": fetched_events,
            "created_activities": created_activities,
            "skipped_events": skipped_events,
        }


    def sync_all_repositories(self, *, per_page: int = 100) -> dict[str, Any]:
        repositories = Repository.objects.select_related("organization").filter(provider__iexact="github").order_by("id")

        results: list[dict[str, Any]] = []
        totals = {
            "repositories": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "fetched_events": 0,
            "created_activities": 0,
            "skipped_events": 0,
        }

        for repository in repositories:
            try:
                result = self.sync_repository(repository, per_page=per_page)
                results.append(result)
                totals["repositories"] += 1
                totals["successful_syncs"] += 1
                totals["fetched_events"] += result.get("fetched_events", 0)
                totals["created_activities"] += result.get("created_activities", 0)
                totals["skipped_events"] += result.get("skipped_events", 0)
            except Exception as exc:
                totals["repositories"] += 1
                totals["failed_syncs"] += 1
                results.append({
                    "repository_id": repository.id,
                    "provider": repository.provider,
                    "name": repository.name,
                    "status": "error",
                    "error": str(exc),
                })

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