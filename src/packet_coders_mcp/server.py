from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from packet_coders_mcp.inventory import load_inventory
from packet_coders_mcp.lab import LabService

DEFAULT_INVENTORY = Path(__file__).resolve().parents[2] / "configs" / "inventory.mock.yaml"
INVENTORY_ENV = "PACKET_CODERS_INVENTORY"

mcp = FastMCP(
    name="Packet Coders Lab",
    instructions=(
        "Use these tools for a disposable EVE-NG or Containerlab network lab. "
        "Prefer health and protocol read tools before making configuration changes."
    ),
)


@lru_cache(maxsize=1)
def get_lab_service() -> LabService:
    inventory_path = os.environ.get(INVENTORY_ENV, str(DEFAULT_INVENTORY))
    return LabService(load_inventory(inventory_path))


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
def list_lab_devices() -> dict[str, Any]:
    """List lab devices available to this MCP server without returning secrets."""
    return get_lab_service().list_devices()


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
    timeout=60,
)
def send_command(device_name: str, command: str) -> dict[str, Any]:
    """Run one read-only show/display command on a lab device.

    Args:
        device_name: Inventory name, such as r1 or spine1.
        command: A read-only show/display command. Configuration commands are blocked.
    """
    return get_lab_service().send_command(device_name, command)


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
    timeout=120,
)
def run_health_check(device_name: str | None = None) -> dict[str, Any]:
    """Run basic health checks against one device, or all devices when omitted.

    Args:
        device_name: Optional inventory device name. If omitted, checks the whole lab.
    """
    return get_lab_service().run_health_check(device_name)


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
    timeout=60,
)
def get_ospf_neighbors(device_name: str) -> dict[str, Any]:
    """Read OSPF neighbors from a lab device using a platform-appropriate command.

    Args:
        device_name: Inventory name, such as r1 or spine1.
    """
    return get_lab_service().get_ospf_neighbors(device_name)


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
    timeout=60,
)
def get_bgp_summary(device_name: str) -> dict[str, Any]:
    """Read BGP summary from a lab device using a platform-appropriate command.

    Args:
        device_name: Inventory name, such as r1 or spine1.
    """
    return get_lab_service().get_bgp_summary(device_name)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    timeout=120,
)
def configure_device(
    device_name: str,
    commands: list[str],
    dry_run: bool = True,
    confirm: bool = False,
) -> dict[str, Any]:
    """Apply config lines to a lab device, with dry-run enabled by default.

    Args:
        device_name: Inventory name, such as r1 or spine1.
        commands: Config lines only. Do not include configure terminal or end.
        dry_run: When true, preview the change without sending config.
        confirm: Must be true with dry_run=false before config is sent.
    """
    return get_lab_service().configure_device(device_name, commands, dry_run, confirm)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
