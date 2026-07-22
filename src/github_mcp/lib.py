"""Embeddable GitHub client — standalone, no dependency on mcp_platform_core.

Reads (search/repo/issues) work unauthenticated but are rate-limited; a token
raises the limit and is required for the write operations (create issue / add
comment). Auth is a static server-side token sent as a Bearer header.

The MCP tool handlers wrap these calls in ``ctx.resilient.call(...)``; auth/tier/
cache/retry concerns live in the platform, so this stays a pure API client.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

GITHUB_API = "https://api.github.com"


class GitHubLibError(Exception):
    """Base error for the GitHub client."""


class MissingTokenError(GitHubLibError):
    """Raised when a write operation is attempted without a token. Never retried."""


class GitHubLib:
    def __init__(
        self, client: httpx.AsyncClient | None = None, *, token: str | None = None
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._owns_client = client is None
        self._token = token

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> GitHubLib:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    def _headers(self, *, require_token: bool = False) -> dict[str, str]:
        if require_token and not self._token:
            raise MissingTokenError("this operation requires GITHUB_TOKEN to be set")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    @staticmethod
    def _repo(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "full_name": row.get("full_name"),
            "description": row.get("description"),
            "stars": row.get("stargazers_count"),
            "forks": row.get("forks_count"),
            "open_issues": row.get("open_issues_count"),
            "language": row.get("language"),
            "url": row.get("html_url"),
        }

    @staticmethod
    def _issue(row: dict[str, Any]) -> dict[str, Any]:
        user = row.get("user") or {}
        return {
            "number": row.get("number"),
            "title": row.get("title"),
            "state": row.get("state"),
            "author": user.get("login"),
            "comments": row.get("comments"),
            "url": row.get("html_url"),
        }

    # ---- Reads (free) -------------------------------------------------------

    async def search_repositories(self, query: str, per_page: int = 5) -> dict[str, Any]:
        response = await self._client.get(
            f"{GITHUB_API}/search/repositories",
            params={"q": query, "per_page": per_page},
            headers=self._headers(),
        )
        response.raise_for_status()
        data = response.json()
        return {
            "query": query,
            "total_count": data.get("total_count"),
            "repositories": [self._repo(r) for r in data.get("items", [])],
        }

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        response = await self._client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}", headers=self._headers()
        )
        response.raise_for_status()
        return self._repo(response.json())

    async def list_issues(self, owner: str, repo: str, per_page: int = 10) -> dict[str, Any]:
        response = await self._client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/issues",
            params={"per_page": per_page},
            headers=self._headers(),
        )
        response.raise_for_status()
        return {
            "repo": f"{owner}/{repo}",
            "issues": [self._issue(r) for r in response.json()],
        }

    # ---- Writes (premium; require token; never cached) ----------------------

    async def create_issue(
        self, owner: str, repo: str, title: str, body: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": title}
        if body is not None:
            payload["body"] = body
        response = await self._client.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/issues",
            json=payload,
            headers=self._headers(require_token=True),
        )
        response.raise_for_status()
        return self._issue(response.json())

    async def add_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> dict[str, Any]:
        response = await self._client.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
            headers=self._headers(require_token=True),
        )
        response.raise_for_status()
        data = response.json()
        user = data.get("user") or {}
        return {
            "id": data.get("id"),
            "issue_number": issue_number,
            "author": user.get("login"),
            "body": data.get("body"),
            "url": data.get("html_url"),
        }
