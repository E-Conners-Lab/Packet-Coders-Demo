from __future__ import annotations

import asyncio

import pytest

from packet_coders_mcp.drivers import NetmikoDriver
from packet_coders_mcp.inventory import inventory_from_mapping
from packet_coders_mcp.lab import LabService, _count_bgp_established_neighbors


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


def test_bgp_count_ignores_arista_router_id_line() -> None:
    # Real Arista EOS output: the "Router identifier ..., local AS number 65004" line
    # ends in the local AS number and has no leading "BGP", so the old heuristic
    # counted it as a 4th neighbor. There are only 3 real neighbors here.
    arista_eos = (
        "BGP summary information for VRF default\n"
        "Router identifier 10.255.0.4, local AS number 65004\n"
        "Neighbor Status Codes: m - Under maintenance\n"
        "  Neighbor   V AS           MsgRcvd   MsgSent  InQ OutQ  Up/Down State   PfxRcd PfxAcc\n"
        "  10.14.14.1 4 65001           6280      6266    0    0    3d16h Estab   3      3\n"
        "  10.24.24.2 4 65002           6257      6273    0    0    3d16h Estab   3      3\n"
        "  10.34.34.3 4 65003           6279      6268    0    0    3d16h Estab   3      3"
    )

    assert _count_bgp_established_neighbors(arista_eos) == 3


def test_run_health_check_covers_whole_lab(lab: LabService) -> None:
    # run_health_check is async and fans out across devices concurrently.
    result = asyncio.run(lab.run_health_check())

    assert set(result["results"]) == {"r1", "spine1"}
    assert all(dev["status"] == "healthy" for dev in result["results"].values())
    # Each device ran its full health bundle (more than zero checks).
    assert all(dev["checks"] for dev in result["results"].values())


def test_run_health_check_single_device(lab: LabService) -> None:
    result = asyncio.run(lab.run_health_check("r1"))

    assert set(result["results"]) == {"r1"}


def test_netmiko_send_commands_reuses_one_session(monkeypatch: pytest.MonkeyPatch) -> None:
    # The health bundle must log in ONCE per device, not once per command.
    inventory = inventory_from_mapping(
        {
            "defaults": {"username": "admin", "password": "admin", "transport": "ssh"},
            "devices": {"sw1": {"host": "192.0.2.1", "platform": "arista_eos"}},
        }
    )
    device = inventory.get("sw1")
    counters = {"connect": 0, "disconnect": 0}

    class FakeConnection:
        def send_command(self, command: str) -> str:
            return f"output: {command}"

        def disconnect(self) -> None:
            counters["disconnect"] += 1

    def fake_connect(_device: object) -> FakeConnection:
        counters["connect"] += 1
        return FakeConnection()

    driver = NetmikoDriver()
    monkeypatch.setattr(driver, "_connect", fake_connect)

    pairs = driver.send_commands(device, ["show a", "show b", "show c"])

    assert counters["connect"] == 1  # one login for three commands
    assert counters["disconnect"] == 1
    assert pairs == [
        ("show a", "output: show a"),
        ("show b", "output: show b"),
        ("show c", "output: show c"),
    ]


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


def test_client_gated_mode_previews_on_dry_run(lab: LabService) -> None:
    # require_confirm_code=False: a dry-run still only previews — no code, no send.
    svc = LabService(lab.inventory, allow_writes=True, require_confirm_code=False)

    result = svc.configure_device("r1", ["interface Loopback100"])

    assert result["applied"] is False
    assert result["would_send"] == ["interface Loopback100"]
    assert "sent" not in result
    assert result.get("pending_confirmation") is None
    assert svc._pending_codes == {}  # no out-of-band code issued in this mode


def test_client_gated_mode_applies_without_code(lab: LabService) -> None:
    # require_confirm_code=False: a non-dry-run call applies directly (the host's
    # per-call approval is the human gate). No confirm_code needed.
    svc = LabService(lab.inventory, allow_writes=True, require_confirm_code=False)
    commands = ["interface Loopback100", "description MCP demo"]

    applied = svc.configure_device("r1", commands, dry_run=False)

    assert applied["applied"] is True
    assert applied["sent"] == commands
    assert "output" in applied
    assert svc._pending_codes == {}


def test_client_gated_mode_still_respects_read_only(lab: LabService) -> None:
    # allow_writes=False wins even in client-gated mode: nothing is ever sent.
    svc = LabService(lab.inventory, allow_writes=False, require_confirm_code=False)

    result = svc.configure_device("r1", ["interface Loopback100"], dry_run=False)

    assert result["applied"] is False
    assert result["writes_enabled"] is False
    assert "sent" not in result
