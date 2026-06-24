from __future__ import annotations

import netmiko

from packet_coders_mcp.drivers import NetmikoDriver
from packet_coders_mcp.inventory import Device


class FakeConn:
    """Minimal stand-in for a netmiko connection that records calls."""

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled
        self.calls: list = []

    def check_enable_mode(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self.calls.append("enable")
        self._enabled = True

    def send_config_set(self, commands: list[str]) -> str:
        self.calls.append(("send_config_set", list(commands)))
        return "applied"

    def disconnect(self) -> None:
        self.calls.append("disconnect")


def _patch_handler(monkeypatch, conn: FakeConn) -> None:
    monkeypatch.setattr(netmiko, "ConnectHandler", lambda **kwargs: conn)


def test_send_config_enables_when_login_is_unprivileged(monkeypatch):
    """Login lands in unprivileged exec (e.g. `Sw3>`) -> enable() before config."""
    conn = FakeConn(enabled=False)
    _patch_handler(monkeypatch, conn)
    dev = Device(name="sw3", host="192.0.2.3", platform="arista_eos")

    NetmikoDriver().send_config(dev, ["interface Loopback100"])

    assert "enable" in conn.calls
    assert conn.calls.index("enable") < conn.calls.index(
        ("send_config_set", ["interface Loopback100"])
    )
    assert "disconnect" in conn.calls


def test_send_config_skips_enable_when_already_privileged(monkeypatch):
    """Already in enable mode -> do not send a redundant enable()."""
    conn = FakeConn(enabled=True)
    _patch_handler(monkeypatch, conn)
    dev = Device(name="sw3", host="192.0.2.3", platform="arista_eos")

    NetmikoDriver().send_config(dev, [])

    assert "enable" not in conn.calls
