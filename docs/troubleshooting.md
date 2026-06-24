# Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Open WebUI tool server shows a red "connection" error; `curl localhost:8000/openapi.json` fails | Host port `8000` is already in use by another service/container | Set `MCPO_PORT=<free port>` in `.env`, `docker compose up -d mcpo`, and add `http://localhost:<port>` in Open WebUI. Check the clash with `lsof -nP -iTCP:8000 -sTCP:LISTEN`. |
| `http://localhost:<port>` shows `{"detail":"Not Found"}` in a browser | Expected — mcpo has no root page | Use `/docs` to browse, or paste the bare base URL into Open WebUI (it appends `/openapi.json`). |
| `docker compose up` rebuilds mcpo instead of pulling | (Fixed in this repo) both `image:` and `build:` were set | `pull_policy: always` now pulls the tested image `ghcr.io/e-conners-lab/packet-coders-mcpo:v1`; `docker compose build mcpo` still rebuilds on demand. See [configuration.md](configuration.md#docker-image). |
| Tools return `r1`/`r2`/`spine1` (`transport: mock`) instead of your gear | Server is still on the **mock** inventory (the default) | Set `PACKET_CODERS_INVENTORY=/app/configs/inventory.local.yaml` in `.env` and `--force-recreate` mcpo. See [real-lab.md](real-lab.md). |
| `qwen3:8b` never downloaded | You used `make up-host`, which uses your **host** Ollama and pulls nothing | `ollama pull qwen3:8b` on the host (or pick a tool-calling model you already have). Only plain `docker compose up` auto-pulls (into the bundled Ollama). |
| SSH `Authentication to device failed … Bad authentication type` | Wrong username/password (most common), **not** the auth method — netmiko/paramiko fall back to `keyboard-interactive` automatically | Fix the creds in `configs/inventory.local.yaml`. Confirm reachability + port first: from the container, `python -c "import socket; socket.create_connection(('<ip>',22),3)"`. |
| `configure_device` 500 / netmiko `ReadTimeout` (`Pattern not detected: '...(config)#'`) | Login lands in unprivileged exec and can't enter config mode | The driver now runs `enable()` automatically when needed; confirm the account can reach enable mode (no enable secret required, or set `enable_password` in the inventory). |
| Model "ignores" the connected tools | Function Calling isn't Native, or context window too small | Model → Advanced Params → **Function Calling → Native**; raise Ollama context (`OLLAMA_CONTEXT_LENGTH=32768`). See [clients.md](clients.md). |
| Edited `.env`/inventory but nothing changed | The server reads inventory at **startup** | Recreate the container: `docker compose up -d --force-recreate mcpo`. A bind-mount updates the file, but the process must restart to reload it. |

> **Run only one of** `docker compose up` **or** `make up-host` **at a time.** They share the
> same Compose project, so the second just reconciles the first — but mixing them mid-debug is
> a good way to confuse yourself about which Ollama (bundled vs host) is actually serving.
