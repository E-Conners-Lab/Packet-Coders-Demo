from __future__ import annotations

import hmac
import re
import secrets
import sys
from dataclasses import dataclass, field
from typing import Any

from packet_coders_mcp.commands import commands_for_platform
from packet_coders_mcp.drivers import driver_for_device
from packet_coders_mcp.inventory import Device, Inventory
from packet_coders_mcp.safety import assert_safe_config_lines, assert_safe_show_command


@dataclass
class LabService:
    inventory: Inventory
    allow_writes: bool = False
    _pending_codes: dict[tuple[str, tuple[str, ...]], str] = field(
        default_factory=dict, init=False, repr=False
    )

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
        confirm_code: str | None = None,
    ) -> dict[str, Any]:
        assert_safe_config_lines(commands)
        device = self.inventory.get(device_name)

        if not self.allow_writes:
            return {
                "device": device.name,
                "dry_run": True,
                "applied": False,
                "writes_enabled": False,
                "would_send": commands,
                "message": (
                    "No config was sent. Writes are disabled on this server. A connected model "
                    "cannot enable them: set PACKET_CODERS_ALLOW_WRITES=true out-of-band."
                ),
            }

        # Writes are enabled, but a real send still needs a one-time confirmation code that is
        # printed only to the server console (stderr) — never returned to the model. A human
        # reads it off the console and supplies it, so the model cannot self-approve a change.
        key = (device_name, tuple(commands))

        if confirm_code is not None:
            expected = self._pending_codes.get(key)
            if expected is not None and hmac.compare_digest(str(confirm_code), expected):
                del self._pending_codes[key]
                output = driver_for_device(device).send_config(device, commands)
                return {
                    "device": device.name,
                    "dry_run": False,
                    "applied": True,
                    "writes_enabled": True,
                    "sent": commands,
                    "output": output,
                }

        code = secrets.token_hex(3).upper()
        self._pending_codes[key] = code
        _emit_confirmation(device, commands, code)
        return {
            "device": device.name,
            "dry_run": True,
            "applied": False,
            "writes_enabled": True,
            "pending_confirmation": True,
            "would_send": commands,
            "message": (
                ("That confirmation code was invalid or expired. " if confirm_code else "")
                + "A one-time confirmation code was printed to the server console (it is NOT "
                "included in this response). Ask the operator to read it, then call "
                "configure_device again with the same commands and confirm_code set to it."
            ),
        }


def _emit_confirmation(device: Device, commands: list[str], code: str) -> None:
    """Print the one-time confirmation code to the server console (stderr only).

    Deliberately uses stderr, never the tool's return value, so the model cannot see the
    code and cannot self-approve a change. A human must read it off the mcpo console.
    """
    banner = "=" * 60
    body = "\n".join(f"    {line}" for line in commands)
    print(
        f"\n{banner}\n"
        f"  CONFIRM CONFIG CHANGE on {device.name} ({device.host})\n{body}\n\n"
        f"  Give the model this confirm_code to apply:  {code}\n"
        f"{banner}",
        file=sys.stderr,
        flush=True,
    )


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
