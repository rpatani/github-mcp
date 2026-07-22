"""Write tools (premium, never cached): create_issue, add_issue_comment.

Writes require GITHUB_TOKEN and the premium tier. They set no cache_ttl_ms —
mutations must never be served from cache.
"""

from __future__ import annotations

from typing import Any

from mcp_platform_core import ToolContext, ToolDefinition
from pydantic import BaseModel, Field

from github_mcp.lib import GitHubLib


class CreateIssueInput(BaseModel):
    owner: str = Field(description="Repository owner/org.")
    repo: str = Field(description="Repository name.")
    title: str = Field(min_length=1, description="Issue title.")
    body: str | None = Field(default=None, description="Optional issue body (Markdown).")


class AddIssueCommentInput(BaseModel):
    owner: str = Field(description="Repository owner/org.")
    repo: str = Field(description="Repository name.")
    issue_number: int = Field(ge=1, description="Issue number to comment on.")
    body: str = Field(min_length=1, description="Comment body (Markdown).")


def make_create_issue_tool(lib: GitHubLib) -> ToolDefinition:
    async def handler(args: CreateIssueInput, ctx: ToolContext) -> dict[str, Any]:
        return await ctx.resilient.call(
            "github",
            lambda: lib.create_issue(args.owner, args.repo, args.title, args.body),
            retries=0,  # never auto-retry a write
        )

    return ToolDefinition(
        name="create_issue",
        description=(
            "Create a new issue in a repository. Premium tier; requires GITHUB_TOKEN. "
            "This is a write operation and is never cached or retried."
        ),
        input_model=CreateIssueInput,
        min_tier="premium",
        cost_units=5,
        cache_ttl_ms=None,
        handler=handler,
    )


def make_add_issue_comment_tool(lib: GitHubLib) -> ToolDefinition:
    async def handler(args: AddIssueCommentInput, ctx: ToolContext) -> dict[str, Any]:
        return await ctx.resilient.call(
            "github",
            lambda: lib.add_issue_comment(args.owner, args.repo, args.issue_number, args.body),
            retries=0,
        )

    return ToolDefinition(
        name="add_issue_comment",
        description=(
            "Add a comment to an existing issue. Premium tier; requires GITHUB_TOKEN. "
            "This is a write operation and is never cached or retried."
        ),
        input_model=AddIssueCommentInput,
        min_tier="premium",
        cost_units=5,
        cache_ttl_ms=None,
        handler=handler,
    )
