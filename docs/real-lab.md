# Connect your own lab

This server talks to **your** network lab over SSH — it doesn't prescribe one. Point it at
whatever you already run: **EVE-NG, CML, GNS3, Containerlab**, or physical gear. Anything the
host can reach by SSH works; you just describe your devices in an inventory file. The
four-switch mesh in [topology.md](topology.md) is only the *reference* lab used in this demo —
you don't need to replicate it or match its addressing.

## Inventory model

Inventory is YAML:

```yaml
defaults:
  username: admin
  password: admin
  port: 22
  platform: cisco_ios
  transport: ssh

devices:
  r1:
    host: 192.0.2.11
    role: edge
  r2:
    host: 192.0.2.12
    role: edge
```

Supported `transport` values:

| Transport | Meaning |
| --- | --- |
| `mock` | Uses built-in demo outputs. No lab required. |
| `ssh` | Uses Netmiko to connect to the device. |

Common `platform` values:

| Platform | Notes |
| --- | --- |
| `cisco_ios`, `cisco_xe`, `ios` | IOS or IOS-XE style commands. |
| `cisco_nxos`, `nxos` | NX-OS style commands. |
| `arista_eos`, `eos` | Arista EOS style commands. |
| `junos`, `juniper_junos` | Junos style commands. |
| `frr`, `linux_frr` | FRR through `vtysh`. |

## Wiring it up

1. Put your lab devices on a management network reachable from the machine running this server.
   (Works the same whether they're EVE-NG, CML, GNS3, Containerlab nodes, or physical gear.)
2. Enable SSH on the nodes (password login is fine — the driver also handles OpenSSH
   `keyboard-interactive`, which is how many Linux-based nodes deliver password auth).
3. Copy the example template to a git-ignored local file and fill in your own `host`,
   `username`, `password`, and `platform` values — add or remove devices to match your lab:

   ```bash
   cp configs/inventory.eve-ng.example.yaml configs/inventory.local.yaml
   ```

**Docker (the quickstart stack):** `configs/` is already mounted into the container, so just
point the server at your file via `.env` and restart mcpo:

```bash
echo 'PACKET_CODERS_INVENTORY=/app/configs/inventory.local.yaml' >> .env
docker compose up -d --force-recreate mcpo   # (or: make up-host)
```

**Native (no Docker):**

```bash
PACKET_CODERS_INVENTORY=configs/inventory.local.yaml uv run packet-coders-mcp
```

Verify it picked up the real lab with `list_lab_devices` — the devices should show
`transport: ssh` and your real hosts (not the `mock-*` names).

See [topology.md](topology.md) for the demo's reference lab (for context — yours can differ),
and [safety.md](safety.md) for how credentials and addresses are kept out of git.
