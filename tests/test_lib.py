"""Tests for the standalone GitHubLib (respx-mocked, no live network)."""

from __future__ import annotations

import httpx
import pytest
import respx

from github_mcp.lib import GITHUB_API, GitHubLib, MissingTokenError


@respx.mock
async def test_search_repositories_maps_items() -> None:
    respx.get(f"{GITHUB_API}/search/repositories").mock(
        return_value=httpx.Response(
            200,
            json={
                "total_count": 2,
                "items": [
                    {
                        "full_name": "awslabs/mcp",
                        "description": "…",
                        "stargazers_count": 100,
                        "forks_count": 10,
                        "open_issues_count": 5,
                        "language": "Python",
                        "html_url": "https://github.com/awslabs/mcp",
                    }
                ],
            },
        )
    )

    async with GitHubLib() as lib:
        result = await lib.search_repositories("mcp")

    assert result["total_count"] == 2
    assert result["repositories"][0]["full_name"] == "awslabs/mcp"
    assert result["repositories"][0]["stars"] == 100


@respx.mock
async def test_get_repo_maps_fields() -> None:
    respx.get(f"{GITHUB_API}/repos/python/cpython").mock(
        return_value=httpx.Response(
            200,
            json={
                "full_name": "python/cpython",
                "description": "The Python programming language",
                "stargazers_count": 73856,
                "forks_count": 34972,
                "open_issues_count": 9456,
                "language": "Python",
                "html_url": "https://github.com/python/cpython",
            },
        )
    )

    async with GitHubLib() as lib:
        result = await lib.get_repo("python", "cpython")

    assert result["stars"] == 73856
    assert result["language"] == "Python"


@respx.mock
async def test_list_issues_maps_and_no_auth_header_without_token() -> None:
    route = respx.get(f"{GITHUB_API}/repos/python/cpython/issues").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "number": 1,
                    "title": "an issue",
                    "state": "open",
                    "user": {"login": "octocat"},
                    "comments": 3,
                    "html_url": "https://github.com/python/cpython/issues/1",
                }
            ],
        )
    )

    async with GitHubLib() as lib:
        result = await lib.list_issues("python", "cpython")

    assert "authorization" not in {k.lower() for k in route.calls.last.request.headers}
    assert result["issues"][0]["author"] == "octocat"


async def test_create_issue_without_token_raises() -> None:
    async with GitHubLib() as lib:
        with pytest.raises(MissingTokenError):
            await lib.create_issue("o", "r", "title")


@respx.mock
async def test_create_issue_sends_bearer_and_payload() -> None:
    route = respx.post(f"{GITHUB_API}/repos/o/r/issues").mock(
        return_value=httpx.Response(
            201,
            json={
                "number": 42,
                "title": "bug",
                "state": "open",
                "user": {"login": "me"},
                "comments": 0,
                "html_url": "https://github.com/o/r/issues/42",
            },
        )
    )

    async with GitHubLib(token="ghp_secret") as lib:
        result = await lib.create_issue("o", "r", "bug", body="details")

    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer ghp_secret"
    import json

    assert json.loads(request.content) == {"title": "bug", "body": "details"}
    assert result["number"] == 42


@respx.mock
async def test_add_issue_comment_sends_bearer() -> None:
    route = respx.post(f"{GITHUB_API}/repos/o/r/issues/42/comments").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": 999,
                "user": {"login": "me"},
                "body": "thanks",
                "html_url": "https://github.com/o/r/issues/42#issuecomment-999",
            },
        )
    )

    async with GitHubLib(token="ghp_secret") as lib:
        result = await lib.add_issue_comment("o", "r", 42, "thanks")

    assert route.calls.last.request.headers["authorization"] == "Bearer ghp_secret"
    assert result["id"] == 999
    assert result["issue_number"] == 42


async def test_add_comment_without_token_raises() -> None:
    async with GitHubLib() as lib:
        with pytest.raises(MissingTokenError):
            await lib.add_issue_comment("o", "r", 1, "hi")


@respx.mock
async def test_http_error_propagates() -> None:
    respx.get(f"{GITHUB_API}/repos/o/r").mock(return_value=httpx.Response(404))

    async with GitHubLib() as lib:
        with pytest.raises(httpx.HTTPStatusError):
            await lib.get_repo("o", "r")
