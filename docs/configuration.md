# Configuration & native (no-Docker) run

## The `.env` file

Docker Compose and `make` read a git-ignored `.env` from the repo root. You only need it to
change a default:

```bash
cp .env.example .env   # then edit
```

| Variable | Default | What it does |
| --- | --- | --- |
| `MCPO_PORT` | `8000` | Host port for the mcpo tool server. Change it if `8000` is already in use (then add `http://localhost:<port>` in Open WebUI). |
| `PACKET_CODERS_INVENTORY` | mock lab | Path **inside the container** to the inventory. Point at `/app/configs/inventory.local.yaml` for a real lab. |
| `PACKET_CODERS_ALLOW_WRITES` | `true` | `false` hides `configure_device` entirely (read-only). |
| `PACKET_CODERS_REQUIRE_CONFIRM_CODE` | `true` | `false` drops the out-of-band code gate so a non-dry-run `configure_device` applies directly — only for hosts that confirm each tool call themselves (Claude Desktop/Code). Leave `true` for auto-executing hosts like Open WebUI (see [safety.md](safety.md)). |
| `OLLAMA_BASE_URL` | bundled Ollama | Model backend. `make up-host` sets this to your host Ollama for you. |
| `LLM_MODEL` | `qwen3:8b` | Model the **bundled** Ollama pulls on `docker compose up`. (Ignored by `make up-host`.) |

## Docker image

The Compose stack pulls a pre-built, multi-arch (`linux/amd64` + `linux/arm64`) image rather
than building locally. It's pinned in `docker-compose.yml`:

```yaml
image: ghcr.io/e-conners-lab/packet-coders-mcpo:v1
pull_policy: always   # always fetch the known-good image on `up`
```

Tags published to GHCR:

| Tag | Meaning |
| --- | --- |
| `:v1` | Rolling "known-good" tag — what Compose pulls. Tracks the latest tested build. |
| `:YYYY-MM-DD[-suffix]` | Immutable dated snapshots for reproducible deploys / rollback (e.g. `:2026-06-24-async`). |

**Pin a fixed build** (instead of the rolling `:v1`) by setting a dated tag in
`docker-compose.yml`:

```yaml
image: ghcr.io/e-conners-lab/packet-coders-mcpo:2026-06-24-async
```

**Rebuild after code changes:** `docker compose build mcpo` rebuilds locally. Maintainers
republish the multi-arch image with:

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/e-conners-lab/packet-coders-mcpo:v1 --push .
```

## Run the server natively (no Docker)

Install the project:

```bash
uv venv
uv pip install -e ".[dev]"
```

Run the server in mock mode (no lab required):

```bash
PACKET_CODERS_INVENTORY=configs/inventory.mock.yaml uv run packet-coders-mcp
```

Or run it through the FastMCP CLI:

```bash
PACKET_CODERS_INVENTORY=configs/inventory.mock.yaml \
  uv run fastmcp run src/packet_coders_mcp/server.py:mcp
```

Run it over HTTP for clients that prefer a URL:

```bash
PACKET_CODERS_INVENTORY=configs/inventory.mock.yaml \
  uv run fastmcp run src/packet_coders_mcp/server.py:mcp --transport http --port 8000
```

HTTP clients then connect to `http://localhost:8000/mcp`.

## Develop

```bash
uv run --extra dev pytest
uv run --extra dev ruff check .
```
