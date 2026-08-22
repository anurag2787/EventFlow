from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class NormalizedEvent:
    activity_type: str
    target_id: str
    source_url: str
    metadata: dict[str, Any]


class GitHubEventNormalizer:
    """Normalizes raw GitHub REST or Webhook event payloads into unified Activity models."""

    def __init__(self) -> None:
        self._dispatch_map: dict[str, Callable[[dict[str, Any]], NormalizedEvent | None]] = {
            "PullRequestEvent": self.normalize_pull_request,
            "IssuesEvent": self.normalize_issue,
            "PushEvent": self.normalize_push,
            "ReleaseEvent": self.normalize_release,
        }

    def normalize(self, payload: dict[str, Any]) -> NormalizedEvent | None:
        if not isinstance(payload, dict):
            return None

        event_type = str(payload.get("type") or "")
        handler = self._dispatch_map.get(event_type)
        if handler:
            return handler(payload)
        return None

    def normalize_pull_request(self, payload: dict[str, Any]) -> NormalizedEvent | None:
        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        action = str(event_payload.get("action") or "")
        pull_request = event_payload.get("pull_request") if isinstance(event_payload.get("pull_request"), dict) else {}
        merged = bool(pull_request.get("merged"))
        number = event_payload.get("number") or pull_request.get("number")

        target_id = str(number or pull_request.get("id") or payload.get("id") or "")
        if not target_id:
            return None

        source_url = self.extract_pull_request_url(payload)

        if action == "opened":
            return self.build_normalized_event(
                activity_type="PR_OPENED",
                target_id=target_id,
                source_url=source_url,
                payload=payload,
            )
        if action == "closed":
            activity_type = "PR_MERGED" if merged else "PR_CLOSED"
            return self.build_normalized_event(
                activity_type=activity_type,
                target_id=target_id,
                source_url=source_url,
                payload=payload,
            )
        return None

    def normalize_issue(self, payload: dict[str, Any]) -> NormalizedEvent | None:
        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        action = str(event_payload.get("action") or "")
        issue = event_payload.get("issue") if isinstance(event_payload.get("issue"), dict) else {}

        target_id = str(issue.get("number") or issue.get("id") or payload.get("id") or "")
        if not target_id:
            return None

        source_url = self.extract_issue_url(payload)

        if action == "opened":
            return self.build_normalized_event(
                activity_type="ISSUE_OPENED",
                target_id=target_id,
                source_url=source_url,
                payload=payload,
            )
        if action == "closed":
            return self.build_normalized_event(
                activity_type="ISSUE_CLOSED",
                target_id=target_id,
                source_url=source_url,
                payload=payload,
            )
        return None

    def normalize_push(self, payload: dict[str, Any]) -> NormalizedEvent | None:
        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        head_commit = event_payload.get("head_commit") if isinstance(event_payload.get("head_commit"), dict) else {}
        ref = str(event_payload.get("ref") or "")

        target_id = str(head_commit.get("id") or payload.get("id") or ref or "")
        if not target_id:
            return None

        return self.build_normalized_event(
            activity_type="COMMIT_PUSHED",
            target_id=target_id,
            source_url=self.extract_commit_url(payload, target_id),
            payload=payload,
        )

    def normalize_release(self, payload: dict[str, Any]) -> NormalizedEvent | None:
        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        action = str(event_payload.get("action") or "")
        release = event_payload.get("release") if isinstance(event_payload.get("release"), dict) else {}

        target_id = str(release.get("id") or payload.get("id") or "")
        if not target_id:
            return None

        if action == "published":
            return self.build_normalized_event(
                activity_type="RELEASE_PUBLISHED",
                target_id=target_id,
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
        repo = payload.get("repo") if isinstance(payload.get("repo"), dict) else {}
        return str(repo.get("name") or "")

    def extract_pull_request_url(self, payload: dict[str, Any]) -> str:
        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        pull_request = event_payload.get("pull_request") if isinstance(event_payload.get("pull_request"), dict) else {}

        html_url = pull_request.get("html_url")
        if isinstance(html_url, str) and html_url:
            return html_url

        repo_name = self.extract_repo_full_name(payload)
        number = event_payload.get("number") or pull_request.get("number")
        return f"https://github.com/{repo_name}/pull/{number}" if repo_name and number else ""

    def extract_issue_url(self, payload: dict[str, Any]) -> str:
        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        issue = event_payload.get("issue") if isinstance(event_payload.get("issue"), dict) else {}

        html_url = issue.get("html_url")
        if isinstance(html_url, str) and html_url:
            return html_url

        repo_name = self.extract_repo_full_name(payload)
        number = issue.get("number")
        return f"https://github.com/{repo_name}/issues/{number}" if repo_name and number else ""

    def extract_release_url(self, payload: dict[str, Any]) -> str:
        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        release = event_payload.get("release") if isinstance(event_payload.get("release"), dict) else {}

        html_url = release.get("html_url")
        if isinstance(html_url, str) and html_url:
            return html_url

        repo_name = self.extract_repo_full_name(payload)
        tag_name = release.get("tag_name")
        return f"https://github.com/{repo_name}/releases/tag/{tag_name}" if repo_name and tag_name else ""

    def extract_commit_url(self, payload: dict[str, Any], sha: str) -> str:
        repo_name = self.extract_repo_full_name(payload)
        return f"https://github.com/{repo_name}/commit/{sha}" if repo_name and sha else ""