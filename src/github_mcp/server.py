"""github-mcp entrypoint: wire the five tools + core deps + transport.

Run with ``uv run github-mcp``. Read tools work unauthenticated (rate-limited);
the two premium write tools require GITHUB_TOKEN, read here (app-level), never in
core, and the premium tier. Transport/keys/metrics are driven by env via CoreConfig.
"""

from __future__ import annotations

import asyncio
import os

from mcp_platform_core import (
    CoreConfig,
    InMemoryRateLimiter,
    InMemoryResponseCache,
    LoggingUsageSink,
    MiddlewareDeps,
    ResilientCaller,
    ToolRegistry,
    build_mcp_server,
    build_metrics,
    create_logger,
    load_key_store,
    run_http,
    run_stdio,
)

from github_mcp.lib import GitHubLib
from github_mcp.tools.reads import (
    make_get_repo_tool,
    make_list_issues_tool,
    make_search_repositories_tool,
)
from github_mcp.tools.writes import make_add_issue_comment_tool, make_create_issue_tool

SERVICE_NAME = "github-mcp"
SERVICE_VERSION = "0.1.0"


def main() -> None:
    config = CoreConfig()
    log = create_logger(
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        transport=config.transport,
        level=config.log_level,
    )
    metrics = build_metrics(config.metrics_backend, enabled=config.metrics_enabled)
    deps = MiddlewareDeps(
        key_store=load_key_store(config.keys_file),
        rate_limiter=InMemoryRateLimiter(),
        cache=InMemoryResponseCache(),
        usage_sink=LoggingUsageSink(log),
        metrics=metrics,
        logger=log,
        resilient=ResilientCaller(
            metrics=metrics,
            timeout_s=config.upstream_timeout_s,
            retries=config.upstream_retries,
            breaker_threshold=config.breaker_threshold,
            breaker_cooldown_s=config.breaker_cooldown_s,
        ),
    )

    # GITHUB_TOKEN is an app-level secret, read here — never in core.
    lib = GitHubLib(token=os.environ.get("GITHUB_TOKEN"))

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

    server = build_mcp_server(
        name=SERVICE_NAME, version=SERVICE_VERSION, registry=registry, deps=deps
    )

    async def _serve() -> None:
        try:
            if config.transport == "stdio":
                await run_stdio(server, api_key=config.api_key, log=log)
            else:
                await run_http(
                    server,
                    port=config.http_port,
                    mcp_path=config.http_path,
                    metrics=metrics,
                    metrics_port=config.metrics_port,
                    log=log,
                )
        finally:
            await lib.aclose()

    asyncio.run(_serve())


if __name__ == "__main__":
    main()
