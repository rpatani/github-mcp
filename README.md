# github-mcp

A GitHub **MCP server** built on
[`mcp-platform-core`](https://github.com/your-org/mcp-platform-py) — consumes the
core as an external, version-pinned library and adds only GitHub tools. It
demonstrates the **static token auth + write operations** style: free read tools
work unauthenticated, and premium write tools use a server-held token gated
behind the `premium` tier. **Writes are never cached or auto-retried.**

## Tools

| Tool | Endpoint | Tier | Cache TTL | Cost |
|---|---|---|---|---|
| `search_repositories` | `GET /search/repositories` | free | 60 s | 1 |
| `get_repo` | `GET /repos/{o}/{r}` | free | 5 min | 1 |
| `list_issues` | `GET /repos/{o}/{r}/issues` | free | 60 s | 1 |
| `create_issue` | `POST …/issues` | premium | — (never cached) | 5 |
| `add_issue_comment` | `POST …/issues/{n}/comments` | premium | — (never cached) | 5 |

Read tools need **no secrets** (rate-limited without a token). Write tools read
`GITHUB_TOKEN` and require the `premium` tier.

## Core dependency

Pinned via git tag in `pyproject.toml`. Local dev resolves from the local
`mcp-platform-py` repo; on push, change the one `git = "file://…"` line to the
GitHub URL.

## Run locally (Mac)

```bash
uv sync

# stdio (read tools keyless)
MCP_TRANSPORT=stdio uv run github-mcp

# HTTP
MCP_TRANSPORT=http MCP_HTTP_PORT=8080 MCP_KEYS_FILE=keys.example.json uv run github-mcp

# smoke test (uses free get_repo only)
./deploy/smoke-test.sh http://localhost:8080 http://localhost:9464
```

To exercise the **write** tools, set `GITHUB_TOKEN` (a fine-grained PAT with
`issues:write`) and call with a `premium`-tier key
(`Authorization: Bearer premium-demo-key`). The write tools genuinely create
issues/comments, so point them at a repo you own.

- MCP endpoint: `POST http://localhost:8080/mcp` · health: `/healthz`, `/readyz`
- Metrics: `http://localhost:9464/metrics`

## Tests & gates

```bash
uv run pytest
uv run ruff check . && uv run mypy .
uv run pip-audit && uv run bandit -r src
```

## Docker

`docker compose -f deploy/docker-compose.yml up --build` — the image build pins
core from git, so switch the local `file://` source to a reachable remote before
building (the container cannot see host paths). For local dev use `uv run`.
