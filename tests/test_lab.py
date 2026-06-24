from __future__ import annotations

import pytest

from packet_coders_mcp.inventory import inventory_from_mapping
from packet_coders_mcp.lab import LabService


@pytest.fixture
def lab() -> LabService:
    inventory = inventory_from_mapping(
        {
            "defaults": {
                "username": "admin",
                "password": "admin",
                "transport": "mock",
                "platform": "cisco_ios",
            },
            "devices": {
                "r1": {"host": "mock-r1"},
                "spine1": {"host": "mock-spine1", "platform": "arista_eos"},
            },
        }
    )
    return LabService(inventory)


def test_list_devices_hides_secrets(lab: LabService) -> None:
    devices = lab.list_devices()["devices"]

    assert devices["r1"]["host"] == "mock-r1"
    assert "password" not in devices["r1"]


def test_send_command_returns_mock_output(lab: LabService) -> None:
    result = lab.send_command("r1", "show ip ospf neighbor")

    assert result["device"] == "r1"
    assert "FULL/DR" in result["output"]


def test_send_command_rejects_config_commands(lab: LabService) -> None:
    with pytest.raises(ValueError, match="read-only"):
        lab.send_command("r1", "configure terminal")


def test_ospf_neighbor_count_hint(lab: LabService) -> None:
    result = lab.get_ospf_neighbors("r1")

    assert result["neighbor_count_hint"] == 2


def test_bgp_established_neighbor_count_hint(lab: LabService) -> None:
    result = lab.get_bgp_summary("r1")

    assert result["established_neighbor_hint"] == 2


def test_configure_device_is_dry_run_by_default(lab: LabService) -> None:
    result = lab.configure_device("r1", ["interface Loopback100", "description MCP demo"])

    assert result["dry_run"] is True
    assert result["would_send"] == ["interface Loopback100", "description MCP demo"]


def test_configure_device_requires_confirm(lab: LabService) -> None:
    result = lab.configure_device(
        "r1",
        ["interface Loopback100", "description MCP demo"],
        dry_run=False,
        confirm=False,
    )

    assert result["dry_run"] is True


def test_configure_device_blocks_dangerous_lines(lab: LabService) -> None:
    with pytest.raises(ValueError, match="Blocked dangerous command"):
        lab.configure_device("r1", ["reload"])


def test_configure_device_blocked_when_writes_disabled(lab: LabService) -> None:
    # Default service has allow_writes=False: even a fully-confirmed call must not send.
    result = lab.configure_device(
        "r1",
        ["no interface Loopback0"],
        dry_run=False,
        confirm=True,
    )

    assert result["dry_run"] is True
    assert result["writes_enabled"] is False
    assert "sent" not in result
    assert "PACKET_CODERS_ALLOW_WRITES" in result["message"]


def test_configure_device_requires_code_when_writes_enabled(lab: LabService) -> None:
    # Even fully "confirmed", a write must not send without the out-of-band code.
    enabled = LabService(lab.inventory, allow_writes=True)

    result = enabled.configure_device(
        "r1",
        ["no interface Loopback0"],
        dry_run=False,
        confirm=True,
    )

    assert result["pending_confirmation"] is True
    assert result["applied"] is False
    assert "sent" not in result


def test_configure_device_applies_with_correct_confirm_code(lab: LabService) -> None:
    enabled = LabService(lab.inventory, allow_writes=True)
    commands = ["interface Loopback100", "description MCP demo"]

    pending = enabled.configure_device("r1", commands)
    assert pending["pending_confirmation"] is True
    assert "sent" not in pending

    code = next(iter(enabled._pending_codes.values()))
    applied = enabled.configure_device("r1", commands, confirm_code=code)

    assert applied["applied"] is True
    assert applied["sent"] == commands
    assert "output" in applied


def test_configure_device_rejects_wrong_confirm_code(lab: LabService) -> None:
    enabled = LabService(lab.inventory, allow_writes=True)
    commands = ["no interface Loopback0"]

    enabled.configure_device("r1", commands)  # issues a real code to the console
    result = enabled.configure_device("r1", commands, confirm_code="DEADBEEF")

    assert result.get("applied") is not True
    assert "sent" not in result


def test_confirm_code_never_appears_in_response(lab: LabService) -> None:
    import json

    enabled = LabService(lab.inventory, allow_writes=True)
    pending = enabled.configure_device("r1", ["interface Loopback123"])
    code = next(iter(enabled._pending_codes.values()))

    # The model must never be able to read the code out of the tool response.
    assert code not in json.dumps(pending)
