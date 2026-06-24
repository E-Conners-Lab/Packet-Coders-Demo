from __future__ import annotations

import asyncio
import hmac
import ipaddress
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
    # When True (default), a real change needs the out-of-band confirmation code printed to
    # the console — right for auto-executing hosts (Open WebUI) where a model could otherwise
    # self-approve. Set False for hosts that confirm every tool call themselves (Claude
    # Desktop / Claude Code): the human approval there is the gate, so apply on a non-dry-run
    # call without a code.
    require_confirm_code: bool = True
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

    async def run_health_check(self, device_name: str | None = None) -> dict[str, Any]:
        """Health-check one device, or every device concurrently when omitted.

        Each device's blocking SSH work runs in its own worker thread, so the lab is
        checked in parallel rather than one login after another. netmiko stays
        synchronous under the hood; asyncio.to_thread is what frees the event loop.
        """
        names = [device_name] if device_name else sorted(self.inventory.devices)
        checks = await asyncio.gather(
            *(asyncio.to_thread(self._check_one_device, name) for name in names)
        )
        return {"results": dict(zip(names, checks, strict=True))}

    def _check_one_device(self, name: str) -> dict[str, Any]:
        # Sync (runs in a worker thread): one login for the whole health bundle.
        device = self.inventory.get(name)
        platform_commands = commands_for_platform(device.platform)
        command_outputs: list[dict[str, str]] = []
        status = "healthy"
        try:
            for command, output in driver_for_device(device).send_commands(
                device, platform_commands.health
            ):
                command_outputs.append({"command": command, "output": output})
        except Exception as exc:  # noqa: BLE001 - login/connection failure for this device
            status = "error"
            command_outputs.append({"error": str(exc)})
        return {
            "device": device.public_dict(),
            "status": status,
            "checks": command_outputs,
        }

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
                    "No config was sent. This server is in read-only mode "
                    "(PACKET_CODERS_ALLOW_WRITES is false); the configure tool is disabled."
                ),
            }

        # Client-gated mode: the host confirms every tool call (Claude Desktop / Claude Code),
        # so that human approval IS the gate. No out-of-band code — apply when the caller asks
        # to (dry_run=False or confirm=True); otherwise return a preview.
        if not self.require_confirm_code:
            if dry_run and not confirm:
                return {
                    "device": device.name,
                    "dry_run": True,
                    "applied": False,
                    "writes_enabled": True,
                    "would_send": commands,
                    "message": (
                        "Preview only (dry_run). Call again with dry_run=false to apply; "
                        "your client will prompt you to approve the change before it is sent."
                    ),
                }
            output = driver_for_device(device).send_config(device, commands)
            return {
                "device": device.name,
                "dry_run": False,
                "applied": True,
                "writes_enabled": True,
                "sent": commands,
                "output": output,
            }

        # Code-gated mode (default): a real send needs a one-time confirmation code that is
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
    # Count only rows whose first column is a neighbor IP address. Anchoring on the
    # neighbor address (rather than "line ends in a digit") avoids miscounting header
    # lines such as Arista EOS's "Router identifier 10.255.0.4, local AS number 65004",
    # which ends in the local AS number and would otherwise look like a neighbor row.
    count = 0
    for line in output.splitlines():
        fields = line.split()
        if not fields:
            continue
        try:
            ipaddress.ip_address(fields[0])
        except ValueError:
            continue
        count += 1
    return count
