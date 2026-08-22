from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .exceptions import (
    GitHubAuthenticationError,
    GitHubClientError,
    GitHubForbiddenError,
    GitHubNetworkError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubServerError,
    GitHubTimeoutError,
)


@dataclass(slots=True)
class GitHubClient:
    token: str | None = None
    base_url: str = "https://api.github.com"
    timeout: int = 15
    user_agent: str = "EventFlow-GitHubClient/1.0"

    def __post_init__(self) -> None:
        if not self.token:
            self.token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")

    def get_repositories(
        self,
        *,
        owner: str | None = None,
        affiliation: str | None = None,
        per_page: int = 30,
        page: int = 1,
    ) -> Any:
        self.validate_pagination(per_page=per_page, page=page)
        if owner:
            path = f"/users/{owner}/repos"
        else:
            path = "/user/repos"

        params = {"per_page": per_page, "page": page}
        if affiliation:
            params["affiliation"] = affiliation
        return self.request("GET", path, params=params)

    def get_repository_events(
        self,
        owner: str,
        repo: str,
        *,
        per_page: int = 30,
        page: int = 1,
    ) -> Any:
        self.validate_pagination(per_page=per_page, page=page)
        return self.request(
            "GET",
            f"/repos/{owner}/{repo}/events",
            params={"per_page": per_page, "page": page},
        )

    def get_pull_requests(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "open",
        per_page: int = 30,
        page: int = 1,
    ) -> Any:
        self.validate_pagination(per_page=per_page, page=page)
        return self.request(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": per_page, "page": page},
        )

    def get_issues(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "open",
        per_page: int = 30,
        page: int = 1,
    ) -> Any:
        self.validate_pagination(per_page=per_page, page=page)
        return self.request(
            "GET",
            f"/repos/{owner}/{repo}/issues",
            params={"state": state, "per_page": per_page, "page": page},
        )

    def get_commits(self, owner: str, repo: str, *, per_page: int = 30, page: int = 1) -> Any:
        self.validate_pagination(per_page=per_page, page=page)
        return self.request(
            "GET",
            f"/repos/{owner}/{repo}/commits",
            params={"per_page": per_page, "page": page},
        )

    def get_releases(self, owner: str, repo: str, *, per_page: int = 30, page: int = 1) -> Any:
        self.validate_pagination(per_page=per_page, page=page)
        return self.request(
            "GET",
            f"/repos/{owner}/{repo}/releases",
            params={"per_page": per_page, "page": page},
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: Any = None,
    ) -> Any:
        url = self.build_url(path, params)
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": self.user_agent,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        request = Request(url, data=data, headers=headers, method=method)

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                if response.status == 204 or not raw:
                    return None

                text = raw.decode(response.headers.get_content_charset() or "utf-8")
                try:
                    return json.loads(text)
                except json.JSONDecodeError as exc:
                    raise GitHubClientError("GitHub API returned invalid JSON") from exc
        except HTTPError as exc:
            self.raise_for_http_error(exc)
        except socket.timeout as exc:
            raise GitHubTimeoutError("GitHub request timed out") from exc
        except URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, socket.timeout):
                raise GitHubTimeoutError("GitHub request timed out") from exc
            raise GitHubNetworkError(f"GitHub network error: {reason}") from exc

        raise GitHubClientError("Unexpected GitHub client state")

    def build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url.rstrip('/')}" + path
        if params:
            query = urlencode({key: value for key, value in params.items() if value is not None})
            if query:
                url = f"{url}?{query}"
        return url

    def validate_pagination(self, *, per_page: int, page: int) -> None:
        if page < 1:
            raise GitHubClientError("page must be greater than or equal to 1")
        if per_page < 1 or per_page > 100:
            raise GitHubClientError("per_page must be between 1 and 100")

    def raise_for_http_error(self, exc: HTTPError) -> None:
        payload = self.read_error_payload(exc)
        message = self.extract_error_message(payload) or f"GitHub API request failed with status {exc.code}"
        retry_after_seconds = self.parse_retry_after(exc.headers.get("Retry-After"))

        if exc.code == 401:
            raise GitHubAuthenticationError(message, status_code=exc.code, payload=payload) from exc
        if exc.code == 403:
            if self.looks_like_rate_limit(payload, exc):
                raise GitHubRateLimitError(
                    message,
                    status_code=exc.code,
                    payload=payload,
                    retry_after=retry_after_seconds,
                ) from exc
            raise GitHubForbiddenError(message, status_code=exc.code, payload=payload) from exc
        if exc.code == 404:
            raise GitHubNotFoundError(message, status_code=exc.code, payload=payload) from exc
        if exc.code == 429:
            raise GitHubRateLimitError(
                message,
                status_code=exc.code,
                payload=payload,
                retry_after=retry_after_seconds,
            ) from exc
        if 500 <= exc.code <= 599:
            raise GitHubServerError(message, status_code=exc.code, payload=payload) from exc

        raise GitHubClientError(message, status_code=exc.code, payload=payload) from exc

    def parse_retry_after(self, retry_after: str | None) -> int | None:
        if not retry_after or not isinstance(retry_after, str):
            return None
        retry_after = retry_after.strip()
        if retry_after.isdigit():
            return int(retry_after)
        try:
            from datetime import datetime, timezone
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(retry_after)
            if dt:
                now = datetime.now(timezone.utc)
                delta = (dt - now).total_seconds()
                return max(0, int(delta))
        except Exception:
            pass
        return None


    def read_error_payload(self, exc: HTTPError) -> Any:
        raw = exc.read()
        if not raw:
            return None
        text = raw.decode(exc.headers.get_content_charset() or "utf-8", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def extract_error_message(self, payload: Any) -> str | None:
        if isinstance(payload, dict):
            if isinstance(payload.get("message"), str):
                return payload["message"]
            if payload.get("errors"):
                return str(payload["errors"])
        if isinstance(payload, str) and payload.strip():
            return payload.strip()
        return None

    def looks_like_rate_limit(self, payload: Any, exc: HTTPError) -> bool:
        if exc.headers.get("X-RateLimit-Remaining") == "0":
            return True
        message = self.extract_error_message(payload)
        return bool(message and "rate limit" in message.lower())
