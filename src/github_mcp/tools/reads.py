"""Read tools (free): search_repositories, get_repo, list_issues."""

from __future__ import annotations

from typing import Any

from mcp_platform_core import ToolContext, ToolDefinition
from pydantic import BaseModel, Field

from github_mcp.lib import GitHubLib

_60S_MS = 60 * 1000
_5MIN_MS = 5 * 60 * 1000


class SearchReposInput(BaseModel):
    query: str = Field(description="GitHub search query, e.g. 'language:python mcp'.")
    per_page: int = Field(default=5, ge=1, le=20, description="Max results (1-20).")


class GetRepoInput(BaseModel):
    owner: str = Field(description="Repository owner/org, e.g. 'python'.")
    repo: str = Field(description="Repository name, e.g. 'cpython'.")


class ListIssuesInput(BaseModel):
    owner: str = Field(description="Repository owner/org.")
    repo: str = Field(description="Repository name.")
    per_page: int = Field(default=10, ge=1, le=30, description="Max issues (1-30).")


def make_search_repositories_tool(lib: GitHubLib) -> ToolDefinition:
    async def handler(args: SearchReposInput, ctx: ToolContext) -> dict[str, Any]:
        return await ctx.resilient.call(
            "github", lambda: lib.search_repositories(args.query, args.per_page)
        )

    return ToolDefinition(
        name="search_repositories",
        description="Search public GitHub repositories by query. Free.",
        input_model=SearchReposInput,
        min_tier="free",
        cost_units=1,
        cache_ttl_ms=_60S_MS,
        handler=handler,
    )


def make_get_repo_tool(lib: GitHubLib) -> ToolDefinition:
    async def handler(args: GetRepoInput, ctx: ToolContext) -> dict[str, Any]:
        return await ctx.resilient.call("github", lambda: lib.get_repo(args.owner, args.repo))

    return ToolDefinition(
        name="get_repo",
        description="Get metadata (stars, forks, language, open issues) for a repository. Free.",
        input_model=GetRepoInput,
        min_tier="free",
        cost_units=1,
        cache_ttl_ms=_5MIN_MS,
        handler=handler,
    )


def make_list_issues_tool(lib: GitHubLib) -> ToolDefinition:
    async def handler(args: ListIssuesInput, ctx: ToolContext) -> dict[str, Any]:
        return await ctx.resilient.call(
            "github", lambda: lib.list_issues(args.owner, args.repo, args.per_page)
        )

    return ToolDefinition(
        name="list_issues",
        description="List open issues for a repository. Free.",
        input_model=ListIssuesInput,
        min_tier="free",
        cost_units=1,
        cache_ttl_ms=_60S_MS,
        handler=handler,
    )
