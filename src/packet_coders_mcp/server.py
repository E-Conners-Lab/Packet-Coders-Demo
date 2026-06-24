from __future__ import annotations

import asyncio
import os
from functools import cache
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from packet_coders_mcp.inventory import load_inventory
from packet_coders_mcp.lab import LabService

DEFAULT_INVENTORY = Path(__file__).resolve().parents[2] / "configs" / "inventory.mock.yaml"
INVENTORY_ENV = "PACKET_CODERS_INVENTORY"
ALLOW_WRITES_ENV = "PACKET_CODERS_ALLOW_WRITES"
REQUIRE_CONFIRM_CODE_ENV = "PACKET_CODERS_REQUIRE_CONFIRM_CODE"


def _writes_enabled() -> bool:
    """Expose configure_device (behind the confirmation gate) unless explicitly read-only.

    Default is on: the tool is registered, but every real change still requires the
    out-of-band confirmation code, so a connected model cannot self-authorize one. Set
    PACKET_CODERS_ALLOW_WRITES to a false-y value (false/0/no/off) for a strictly
    read-only server that does not expose the tool at all.
    """
    value = os.environ.get(ALLOW_WRITES_ENV, "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _require_confirm_code() -> bool:
    """Require the out-of-band confirmation code for a real change (default on).

    Keep on for auto-executing hosts (Open WebUI), where a model could otherwise self-approve.
    Set PACKET_CODERS_REQUIRE_CONFIRM_CODE to a false-y value for hosts that confirm every tool
    call themselves (Claude Desktop / Claude Code) — there the per-call approval is the gate.
    """
    value = os.environ.get(REQUIRE_CONFIRM_CODE_ENV, "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


mcp = FastMCP(
    name="Packet Coders Lab",
    instructions=(
        "Use these tools for a disposable EVE-NG or Containerlab network lab. "
        "Prefer health and protocol read tools before making configuration changes."
    ),
)


# Lazy singleton: build the LabService (parse inventory, open device sessions)
# on first use and reuse that one instance for the life of the process.
# @cache memoizes the zero-arg call, so every tool shares the same service.
# Call get_lab_service.cache_clear() to force a rebuild (e.g. after swapping
# PACKET_CODERS_INVENTORY or in test fixtures).
@cache
def get_lab_service() -> LabService:
    inventory_path = os.environ.get(INVENTORY_ENV, str(DEFAULT_INVENTORY))
    return LabService(
        load_inventory(inventory_path),
        allow_writes=_writes_enabled(),
        require_confirm_code=_require_confirm_code(),
    )


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def list_lab_devices() -> dict[str, Any]:
    """List lab devices available to this MCP server without returning secrets."""
    # Pure in-memory lookup — no device I/O, so no thread offload needed.
    return get_lab_service().list_devices()


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
    timeout=60,
)
async def send_command(device_name: str, command: str) -> dict[str, Any]:
    """Run one read-only show/display command on a lab device.

    Args:
        device_name: Inventory device name (case-insensitive). Call list_lab_devices
            first to get the exact names — do not guess.
        command: A read-only show/display command. Configuration commands are blocked.
    """
    # netmiko's SSH call is blocking; run it in a worker thread so the event loop
    # stays free to service other tool calls concurrently.
    return await asyncio.to_thread(get_lab_service().send_command, device_name, command)


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
    timeout=120,
)
async def run_health_check(device_name: str | None = None) -> dict[str, Any]:
    """Run basic health checks against one device, or all devices when omitted.

    Args:
        device_name: Optional inventory device name (case-insensitive). If omitted, checks
            the whole lab. Call list_lab_devices first to get exact names — do not guess.
    """
    # LabService.run_health_check fans out across devices concurrently (one thread per
    # device), so a whole-lab check is N parallel logins rather than N serial ones.
    return await get_lab_service().run_health_check(device_name)


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
    timeout=60,
)
async def get_ospf_neighbors(device_name: str) -> dict[str, Any]:
    """Read OSPF neighbors from a lab device using a platform-appropriate command.

    Args:
        device_name: Inventory device name (case-insensitive). Call list_lab_devices
            first to get the exact names — do not guess.
    """
    return await asyncio.to_thread(get_lab_service().get_ospf_neighbors, device_name)


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
    timeout=60,
)
async def get_bgp_summary(device_name: str) -> dict[str, Any]:
    """Read BGP summary from a lab device using a platform-appropriate command.

    Args:
        device_name: Inventory device name (case-insensitive). Call list_lab_devices
            first to get the exact names — do not guess.
    """
    return await asyncio.to_thread(get_lab_service().get_bgp_summary, device_name)


async def configure_device(
    device_name: str,
    commands: list[str],
    dry_run: bool = True,
    confirm: bool = False,
    confirm_code: str | None = None,
) -> dict[str, Any]:
    """Apply config lines to a lab device behind a two-step human confirmation gate.

    Step 1 - call WITHOUT confirm_code: returns a preview and prints a one-time
    confirmation code to the SERVER CONSOLE only (never in this response). Step 2 - a
    human reads that code off the console and you call again with the same commands and
    confirm_code set to it. Only then is config sent. The model never sees the code, so it
    cannot self-approve. Exposed by default; set PACKET_CODERS_ALLOW_WRITES=false for a
    read-only server where this tool is not present at all.

    Args:
        device_name: Inventory device name (case-insensitive). Call list_lab_devices
            first to get the exact names — do not guess.
        commands: Config lines only. Do not include configure terminal or end.
        dry_run: Legacy preview flag; the confirm_code step now governs sending.
        confirm: Legacy flag; superseded by confirm_code.
        confirm_code: The one-time code shown on the server console for THIS change.
    """
    # The send_config path is blocking netmiko I/O; offload it to a thread.
    return await asyncio.to_thread(
        get_lab_service().configure_device,
        device_name,
        commands,
        dry_run,
        confirm,
        confirm_code,
    )


# configure_device is exposed by default, but always behind the out-of-band confirmation
# gate (a model can't self-approve). Launch with PACKET_CODERS_ALLOW_WRITES=false for a
# strictly read-only server, where the tool is never advertised at all.
if _writes_enabled():
    configure_device = mcp.tool(
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        timeout=120,
    )(configure_device)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
