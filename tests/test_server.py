"""Server wiring tests: tools listed, free read runs, write tools gated + never cached."""

from __future__ import annotations

import json

import httpx
import respx
import structlog
from mcp.shared.memory import create_connected_server_and_client_session
from mcp_platform_core import (
    ApiKeyRecord,
    InMemoryKeyStore,
    InMemoryRateLimiter,
    InMemoryResponseCache,
    LoggingUsageSink,
    MiddlewareDeps,
    NullMetrics,
    ResilientCaller,
    ToolRegistry,
    build_mcp_server,
)
from mcp_platform_core.server import current_api_key

from github_mcp.lib import GITHUB_API, GitHubLib
from github_mcp.tools.reads import (
    make_get_repo_tool,
    make_list_issues_tool,
    make_search_repositories_tool,
)
from github_mcp.tools.writes import make_add_issue_comment_tool, make_create_issue_tool

EXPECTED_TOOLS = {
    "search_repositories",
    "get_repo",
    "list_issues",
    "create_issue",
    "add_issue_comment",
}


def _build(lib: GitHubLib):
    keys = InMemoryKeyStore(
        {
            "premium-key": ApiKeyRecord(
                api_key="premium-key", owner="pro", tier="premium", rate_limit_per_minute=100
            )
        }
    )
    deps = MiddlewareDeps(
        key_store=keys,
        rate_limiter=InMemoryRateLimiter(),
        cache=InMemoryResponseCache(),
        usage_sink=LoggingUsageSink(structlog.get_logger()),
        metrics=NullMetrics(),
        logger=structlog.get_logger(),
        resilient=ResilientCaller(),
    )
    registry = ToolRegistry()
    registry.register_all(
        [
            make_search_repositories_tool(lib),
            make_get_repo_tool(lib),
            make_list_issues_tool(lib),
            make_create_issue_tool(lib),
            make_add_issue_comment_tool(lib),
        ]
    )
    return build_mcp_server(name="github-mcp", version="0.1.0", registry=registry, deps=deps)


async def test_lists_all_five_tools() -> None:
    server = _build(GitHubLib())
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_tools()
    assert {t.name for t in result.tools} == EXPECTED_TOOLS


@respx.mock
async def test_free_read_runs() -> None:
    respx.get(f"{GITHUB_API}/repos/python/cpython").mock(
        return_value=httpx.Response(
            200, json={"full_name": "python/cpython", "stargazers_count": 100}
        )
    )
    server = _build(GitHubLib())
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("get_repo", {"owner": "python", "repo": "cpython"})

    assert result.isError is False
    assert json.loads(result.content[0].text)["stars"] == 100


async def test_write_tool_rejected_for_anonymous() -> None:
    server = _build(GitHubLib(token="ghp_x"))
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("create_issue", {"owner": "o", "repo": "r", "title": "hi"})
    assert result.isError is True
    assert "tier" in result.content[0].text.lower()


@respx.mock
async def test_write_tool_allowed_with_premium_key_and_not_cached() -> None:
    route = respx.post(f"{GITHUB_API}/repos/o/r/issues").mock(
        return_value=httpx.Response(201, json={"number": 7, "title": "hi", "user": {"login": "me"}})
    )
    server = _build(GitHubLib(token="ghp_x"))
    token = current_api_key.set("premium-key")
    try:
        async with create_connected_server_and_client_session(server) as client:
            r1 = await client.call_tool("create_issue", {"owner": "o", "repo": "r", "title": "hi"})
            r2 = await client.call_tool("create_issue", {"owner": "o", "repo": "r", "title": "hi"})
    finally:
        current_api_key.reset(token)

    assert r1.isError is False and r2.isError is False
    # Writes are never cached: identical calls must both hit the upstream.
    assert route.call_count == 2
    assert json.loads(r1.content[0].text)["number"] == 7
