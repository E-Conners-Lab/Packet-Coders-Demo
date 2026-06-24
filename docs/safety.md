# Safety Model

This is a demo server, not a production change platform. Its guardrails, strongest first:

- **Every real change needs an out-of-band confirmation code the model never sees.** The first
  `configure_device` call returns a preview and prints a one-time code to the **server console
  (stderr) only** — never in the tool response. To apply, a human reads that code off the console
  and calls again with `confirm_code` set to it. Because the code never reaches the model, the
  model **cannot self-approve**, even on an auto-executing host like Open WebUI. This is the
  human-in-the-loop gate, and it works with **any** model (Qwen included) and **any** client.
- **Read-only is one flag.** `configure_device` is exposed by default (behind that gate). Start the
  server with `PACKET_CODERS_ALLOW_WRITES=false` for a strictly read-only deployment, where the tool
  is **not even advertised** — an auto-executing host never sees it. That flag is read from the
  process environment, so **a connected model cannot change it.**
- **Or use a host that confirms each tool call.** Claude Desktop / Claude Code additionally prompt
  you to approve every tool call — a second, host-level way to keep a human in the loop. With such
  a host you can make *its* approval the gate and skip the code: set
  `PACKET_CODERS_REQUIRE_CONFIRM_CODE=false` **in that client's own server config** (e.g. the `env`
  block of its `claude_desktop_config.json` entry). Then `configure_device` applies on a non-dry-run
  call, and the client's "approve this tool call?" prompt is the human gate. Leave it at the default
  (`true`) for auto-executing hosts like Open WebUI, where the out-of-band code is what stops a model
  from self-approving. The flag is read from the process environment, so a connected model can't
  change it.
- `send_command` blocks obvious config and destructive commands.
- Dangerous config lines such as `reload`, `erase`, `delete`, and `write erase` are blocked — but
  ordinary `no …` lines (e.g. removing a loopback) are **not**, which is why the confirmation-code
  gate above is the real control.
- Do not point this at production networks.

## Keeping the lab private

This repo and the committed configs deliberately contain **no real credentials, no real
management IPs, and no machine-specific paths**:

- Real credentials and management addresses live only in `inventory.local.yaml`, which is
  git-ignored. The committed `configs/*.yaml` use `admin/admin` placeholders and the RFC 5737
  documentation range (`192.0.2.0/24`).
- Client configs that hold your absolute paths or tailnet hostnames go in `mcp.local.json`
  (also git-ignored). Keep `<ABSOLUTE_PATH_TO_REPO>` / `<your-tailnet-host>` as placeholders
  in anything you commit or share.
- Keep your inference backends (Ollama/vLLM) on the tailnet, never exposed to the public
  internet — an open Ollama/vLLM port is an unauthenticated model and tool surface.
- In-fabric OSPF/loopback addresses (`10.x`) are safe to share; your real management subnet
  is not — don't paste it into docs.
