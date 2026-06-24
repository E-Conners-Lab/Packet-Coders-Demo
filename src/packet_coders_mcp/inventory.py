from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Device:
    name: str
    host: str
    platform: str = "cisco_ios"
    username: str = "admin"
    password: str = "admin"
    port: int = 22
    transport: str = "ssh"
    role: str | None = None
    enable_password: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        """Return device details without secrets."""
        return {
            "name": self.name,
            "host": self.host,
            "platform": self.platform,
            "port": self.port,
            "transport": self.transport,
            "role": self.role,
        }


@dataclass(frozen=True)
class Inventory:
    devices: dict[str, Device]

    def get(self, name: str) -> Device:
        # Exact match first (fast path), then a case-insensitive fallback: lab/EVE-NG/CML
        # node names are inconsistently cased, and tool-callers — especially local models —
        # routinely send "SW1" when the inventory says "sw1". The returned Device keeps its
        # canonical name, so responses always echo the inventory's spelling.
        device = self.devices.get(name)
        if device is not None:
            return device

        lowered = name.lower()
        for device in self.devices.values():
            if device.name.lower() == lowered:
                return device

        known = ", ".join(sorted(self.devices)) or "none"
        raise ValueError(f"Unknown device {name!r}. Known devices: {known}")

    def public_dict(self) -> dict[str, Any]:
        return {"devices": {name: device.public_dict() for name, device in self.devices.items()}}


def load_inventory(path: str | Path) -> Inventory:
    """Load an inventory file from YAML or JSON."""
    inventory_path = Path(path).expanduser()
    if not inventory_path.exists():
        raise FileNotFoundError(f"Inventory file not found: {inventory_path}")

    if inventory_path.suffix.lower() == ".json":
        data = json.loads(inventory_path.read_text())
    else:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("Install PyYAML to load YAML inventory files.") from exc
        data = yaml.safe_load(inventory_path.read_text()) or {}

    return inventory_from_mapping(data)


def inventory_from_mapping(data: dict[str, Any]) -> Inventory:
    defaults = data.get("defaults") or {}
    raw_devices = data.get("devices") or {}

    devices: dict[str, Device] = {}
    for name, raw_device in raw_devices.items():
        if not isinstance(raw_device, dict):
            raise ValueError(f"Device {name!r} must be a mapping.")
        merged = {**defaults, **raw_device}
        if "host" not in merged:
            raise ValueError(f"Device {name!r} is missing required field 'host'.")

        known_fields = {
            "host",
            "platform",
            "username",
            "password",
            "port",
            "transport",
            "role",
            "enable_password",
        }
        extras = {key: value for key, value in merged.items() if key not in known_fields}
        devices[name] = Device(
            name=name,
            host=str(merged["host"]),
            platform=str(merged.get("platform", "cisco_ios")),
            username=str(merged.get("username", "admin")),
            password=str(merged.get("password", "admin")),
            port=int(merged.get("port", 22)),
            transport=str(merged.get("transport", "ssh")),
            role=merged.get("role"),
            enable_password=merged.get("enable_password"),
            extras=extras,
        )

    if not devices:
        raise ValueError("Inventory must define at least one device.")
    return Inventory(devices=devices)
