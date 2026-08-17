from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class NormalizedEvent:
    activity_type: str
    target_id: str
    source_url: str
    metadata: dict[str, Any]


class GitHubEventNormalizer:
    def normalize(self, payload: dict[str, Any]) -> NormalizedEvent | None:
        event_type = str(payload.get("type") or "")

        if event_type == "PullRequestEvent":
            return self.normalize_pull_request(payload)
        if event_type == "IssuesEvent":
            return self.normalize_issue(payload)
        if event_type == "PushEvent":
            return self.normalize_push(payload)
        if event_type == "ReleaseEvent":
            return self.normalize_release(payload)

        return None

    def normalize_pull_request(self, payload: dict[str, Any]) -> NormalizedEvent | None:
        action = str((payload.get("payload") or {}).get("action") or "")
        merged = bool((payload.get("payload") or {}).get("pull_request", {}).get("merged"))
        number = (payload.get("payload") or {}).get("number")
        pull_request = (payload.get("payload") or {}).get("pull_request") or {}

        if action == "opened":
            return self.build_normalized_event(
                activity_type="PR_OPENED",
                target_id=str(number or pull_request.get("id") or payload.get("id")),
                source_url=self.extract_pull_request_url(payload),
                payload=payload,
            )
        if action == "closed" and merged:
            return self.build_normalized_event(
                activity_type="PR_MERGED",
                target_id=str(number or pull_request.get("id") or payload.get("id")),
                source_url=self.extract_pull_request_url(payload),
                payload=payload,
            )
        if action == "closed":
            return self.build_normalized_event(
                activity_type="PR_CLOSED",
                target_id=str(number or pull_request.get("id") or payload.get("id")),
                source_url=self.extract_pull_request_url(payload),
                payload=payload,
            )
        return None

    def normalize_issue(self, payload: dict[str, Any]) -> NormalizedEvent | None:
        issue_payload = payload.get("payload") or {}
        action = str(issue_payload.get("action") or "")
        issue = issue_payload.get("issue") or {}

        if action == "opened":
            return self.build_normalized_event(
                activity_type="ISSUE_OPENED",
                target_id=str(issue.get("number") or issue.get("id") or payload.get("id")),
                source_url=self.extract_issue_url(payload),
                payload=payload,
            )
        if action == "closed":
            return self.build_normalized_event(
                activity_type="ISSUE_CLOSED",
                target_id=str(issue.get("number") or issue.get("id") or payload.get("id")),
                source_url=self.extract_issue_url(payload),
                payload=payload,
            )
        return None

    def normalize_push(self, payload: dict[str, Any]) -> NormalizedEvent | None:
        event_payload = payload.get("payload") or {}
        head_commit = event_payload.get("head_commit") or {}
        ref = str(event_payload.get("ref") or "")

        target_id = str(head_commit.get("id") or payload.get("id") or ref)
        return self.build_normalized_event(
            activity_type="COMMIT_PUSHED",
            target_id=target_id,
            source_url=self.extract_commit_url(payload, target_id),
            payload=payload,
        )

    def normalize_release(self, payload: dict[str, Any]) -> NormalizedEvent | None:
        event_payload = payload.get("payload") or {}
        action = str(event_payload.get("action") or "")
        release = event_payload.get("release") or {}

        if action == "published":
            return self.build_normalized_event(
                activity_type="RELEASE_PUBLISHED",
                target_id=str(release.get("id") or payload.get("id")),
                source_url=self.extract_release_url(payload),
                payload=payload,
            )
        return None

    def build_normalized_event(
        self,
        *,
        activity_type: str,
        target_id: str,
        source_url: str,
        payload: dict[str, Any],
    ) -> NormalizedEvent:
        return NormalizedEvent(
            activity_type=activity_type,
            target_id=target_id,
            source_url=source_url,
            metadata={
                "source_provider": "github",
                "source_event_type": payload.get("type"),
                "source_event_id": payload.get("id"),
                "payload": payload,
            },
        )

    def extract_repo_full_name(self, payload: dict[str, Any]) -> str:
        repo = payload.get("repo") or {}
        return str(repo.get("name") or "")

    def extract_pull_request_url(self, payload: dict[str, Any]) -> str:
        pull_request = (payload.get("payload") or {}).get("pull_request") or {}
        if isinstance(pull_request.get("html_url"), str) and pull_request["html_url"]:
            return pull_request["html_url"]
        repo_name = self.extract_repo_full_name(payload)
        number = (payload.get("payload") or {}).get("number") or pull_request.get("number")
        return f"https://github.com/{repo_name}/pull/{number}" if repo_name and number else ""

    def extract_issue_url(self, payload: dict[str, Any]) -> str:
        issue = (payload.get("payload") or {}).get("issue") or {}
        if isinstance(issue.get("html_url"), str) and issue["html_url"]:
            return issue["html_url"]
        repo_name = self.extract_repo_full_name(payload)
        number = issue.get("number")
        return f"https://github.com/{repo_name}/issues/{number}" if repo_name and number else ""

    def extract_release_url(self, payload: dict[str, Any]) -> str:
        release = (payload.get("payload") or {}).get("release") or {}
        if isinstance(release.get("html_url"), str) and release["html_url"]:
            return release["html_url"]
        repo_name = self.extract_repo_full_name(payload)
        tag_name = release.get("tag_name")
        return f"https://github.com/{repo_name}/releases/tag/{tag_name}" if repo_name and tag_name else ""

    def extract_commit_url(self, payload: dict[str, Any], sha: str) -> str:
        repo_name = self.extract_repo_full_name(payload)
        return f"https://github.com/{repo_name}/commit/{sha}" if repo_name and sha else ""