# From Chat to MCP: A Network Engineer's MCP Lab

A compact demo MCP server (FastMCP) that lets an LLM safely drive a network lab. Runs in
**mock mode** with no hardware, or against a real EVE-NG lab by swapping one inventory file.
Works from Claude Code, Claude Desktop, or a fully local LLM stack (Ollama / vLLM).

| Tool | Purpose |
| --- | --- |
| `list_lab_devices` | Show the inventory the server can reach. |
| `send_command` | Run a read-only show command on one device. |
| `run_health_check` | Health bundle against one device or the whole lab. |
| `get_ospf_neighbors` | OSPF neighbor state (right command per platform). |
| `get_bgp_summary` | BGP summary state (right command per platform). |
| `configure_device` | Push config — gated by an out-of-band confirm code (read-only is one flag). |

## Quickstart (Docker)

Spins up the whole stack — chat UI, lab tools, and a local model — with one command.

```bash
git clone https://github.com/E-Conners-Lab/Packet-Coders-Demo.git
cd Packet-Coders-Demo
docker compose up        # first run pulls images + the qwen3:8b model (a few minutes)
```

Open **http://localhost:3000** (no login) → **Settings → Integrations** → add
`http://localhost:8000` as a tool server → set the model's **Function Calling → Native** →
ask *"list the lab devices."* Defaults to the **mock lab** (no hardware needed).

| Want… | Do this |
| --- | --- |
| Faster on a Mac (host Ollama, Metal GPU) | `make up-host` (then `ollama pull qwen3:8b` yourself) |
| The real EVE-NG lab | [docs/real-lab.md](docs/real-lab.md) |
| Change port / model / inventory | copy `.env.example` → `.env` — [docs/configuration.md](docs/configuration.md) |
| Read-only (hide the write tool) | `make readonly` |
| Stop everything | `make down` |

> Port `8000` already in use? Set `MCPO_PORT` in `.env`. More fixes in
> [docs/troubleshooting.md](docs/troubleshooting.md).

## Connect a client

Point any MCP client at the server (start with the mock inventory). Full per-client steps —
Claude Code, Claude Desktop, Ollama / vLLM + Open WebUI — are in **[docs/clients.md](docs/clients.md)**.

```bash
# Claude Code, from the repo root:
claude mcp add packet-coders-lab \
  --env PACKET_CODERS_INVENTORY="$PWD/configs/inventory.mock.yaml" \
  -- uv run --project "$PWD" packet-coders-mcp
```

Verify with `claude mcp list`, then ask it to `list_lab_devices`.

## Safety

A demo, not a production change tool. Strongest guardrails:

- **Writes need an out-of-band code the model never sees** — `configure_device` prints a
  one-time code to the server console; a human reads it back, so the model can't self-approve.
- **Read-only is one flag** — `PACKET_CODERS_ALLOW_WRITES=false` hides the write tool entirely.
- **Hosts that confirm each call** (Claude Desktop / Code) can use their own approval instead —
  set `PACKET_CODERS_REQUIRE_CONFIRM_CODE=false`.

Don't point it at production. Full model: [docs/safety.md](docs/safety.md).

## Docs

- [docs/clients.md](docs/clients.md) — connect Claude Code / Desktop / Ollama / vLLM + Open WebUI
- [docs/real-lab.md](docs/real-lab.md) — inventory model + EVE-NG setup + keeping creds private
- [docs/configuration.md](docs/configuration.md) — every `.env` knob + native (no-Docker) run
- [docs/topology.md](docs/topology.md) — the four-switch reference lab (OSPF + eBGP)
- [docs/safety.md](docs/safety.md) — full guardrail model
- [docs/troubleshooting.md](docs/troubleshooting.md) — common errors and fixes

## Develop

```bash
uv run --extra dev pytest
uv run --extra dev ruff check .
```
