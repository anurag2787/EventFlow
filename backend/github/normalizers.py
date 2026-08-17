from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class NormalizedEvent:
    activity_type: str
    target_id: str
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
                payload=payload,
            )
        if action == "closed" and merged:
            return self.build_normalized_event(
                activity_type="PR_MERGED",
                target_id=str(number or pull_request.get("id") or payload.get("id")),
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
                payload=payload,
            )
        return None

    def build_normalized_event(
        self,
        *,
        activity_type: str,
        target_id: str,
        payload: dict[str, Any],
    ) -> NormalizedEvent:
        return NormalizedEvent(
            activity_type=activity_type,
            target_id=target_id,
            metadata={
                "source_provider": "github",
                "source_event_type": payload.get("type"),
                "source_event_id": payload.get("id"),
                "payload": payload,
            },
        )