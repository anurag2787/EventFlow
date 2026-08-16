from __future__ import annotations


class GitHubClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class GitHubAuthenticationError(GitHubClientError):
    pass


class GitHubForbiddenError(GitHubClientError):
    pass


class GitHubNotFoundError(GitHubClientError):
    pass


class GitHubRateLimitError(GitHubClientError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload=None,
        retry_after: int | None = None,
    ):
        super().__init__(message, status_code=status_code, payload=payload)
        self.retry_after = retry_after


class GitHubServerError(GitHubClientError):
    pass


class GitHubTimeoutError(GitHubClientError):
    pass


class GitHubNetworkError(GitHubClientError):
    pass
