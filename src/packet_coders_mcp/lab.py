from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from packet_coders_mcp.commands import commands_for_platform
from packet_coders_mcp.drivers import driver_for_device
from packet_coders_mcp.inventory import Inventory
from packet_coders_mcp.safety import assert_safe_config_lines, assert_safe_show_command


@dataclass
class LabService:
    inventory: Inventory

    def list_devices(self) -> dict[str, Any]:
        return self.inventory.public_dict()

    def send_command(self, device_name: str, command: str) -> dict[str, Any]:
        assert_safe_show_command(command)
        device = self.inventory.get(device_name)
        output = driver_for_device(device).send_command(device, command)
        return {
            "device": device.name,
            "host": device.host,
            "platform": device.platform,
            "command": command,
            "output": output,
        }

    def run_health_check(self, device_name: str | None = None) -> dict[str, Any]:
        names = [device_name] if device_name else sorted(self.inventory.devices)
        results: dict[str, Any] = {}
        for name in names:
            device = self.inventory.get(name)
            platform_commands = commands_for_platform(device.platform)
            command_outputs = []
            status = "healthy"
            for command in platform_commands.health:
                try:
                    output = driver_for_device(device).send_command(device, command)
                    command_outputs.append({"command": command, "output": output})
                except Exception as exc:  # noqa: BLE001 - tool responses should be user-readable
                    status = "error"
                    command_outputs.append({"command": command, "error": str(exc)})
            results[name] = {
                "device": device.public_dict(),
                "status": status,
                "checks": command_outputs,
            }
        return {"results": results}

    def get_ospf_neighbors(self, device_name: str) -> dict[str, Any]:
        device = self.inventory.get(device_name)
        command = commands_for_platform(device.platform).ospf_neighbors
        output = driver_for_device(device).send_command(device, command)
        return {
            "device": device.name,
            "command": command,
            "neighbor_count_hint": _count_ospf_neighbors(output),
            "output": output,
        }

    def get_bgp_summary(self, device_name: str) -> dict[str, Any]:
        device = self.inventory.get(device_name)
        command = commands_for_platform(device.platform).bgp_summary
        output = driver_for_device(device).send_command(device, command)
        return {
            "device": device.name,
            "command": command,
            "established_neighbor_hint": _count_bgp_established_neighbors(output),
            "output": output,
        }

    def configure_device(
        self,
        device_name: str,
        commands: list[str],
        dry_run: bool = True,
        confirm: bool = False,
    ) -> dict[str, Any]:
        assert_safe_config_lines(commands)
        device = self.inventory.get(device_name)
        if dry_run or not confirm:
            return {
                "device": device.name,
                "dry_run": True,
                "would_send": commands,
                "message": "No config was sent. Set dry_run=False and confirm=True to apply.",
            }

        output = driver_for_device(device).send_config(device, commands)
        return {
            "device": device.name,
            "dry_run": False,
            "sent": commands,
            "output": output,
        }


def _count_ospf_neighbors(output: str) -> int:
    count = 0
    for line in output.splitlines():
        if re.search(r"\bFULL/", line):
            count += 1
    return count


def _count_bgp_established_neighbors(output: str) -> int:
    count = 0
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith(("neighbor", "bgp ")):
            continue
        fields = stripped.split()
        if fields and fields[-1].isdigit():
            count += 1
    return count
