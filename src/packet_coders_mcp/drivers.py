from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from packet_coders_mcp.inventory import Device


class NetworkDriver(ABC):
    @abstractmethod
    def send_command(self, device: Device, command: str) -> str:
        """Run an operational command and return device output."""

    @abstractmethod
    def send_config(self, device: Device, commands: list[str]) -> str:
        """Send configuration commands and return device output."""


class MockNetworkDriver(NetworkDriver):
    """Deterministic lab output for demos without a reachable network lab."""

    def send_command(self, device: Device, command: str) -> str:
        key = command.strip().lower()
        if "ospf" in key and "neighbor" in key:
            return _mock_ospf(device)
        if "bgp" in key and "summary" in key:
            return _mock_bgp(device)
        if "interface brief" in key:
            return _mock_interfaces(device)
        if "route summary" in key:
            return _mock_routes(device)
        if "version" in key:
            return _mock_version(device)
        return f"{device.name}# {command}\nMock output for {device.name} ({device.platform})."

    def send_config(self, device: Device, commands: list[str]) -> str:
        rendered = "\n".join(f"  {line}" for line in commands)
        return f"{device.name} accepted mock config lines:\n{rendered}"


class NetmikoDriver(NetworkDriver):
    """Netmiko-backed SSH driver for EVE-NG, Containerlab, or similar labs."""

    def send_command(self, device: Device, command: str) -> str:
        connection = self._connect(device)
        try:
            return str(connection.send_command(command))
        finally:
            connection.disconnect()

    def send_config(self, device: Device, commands: list[str]) -> str:
        connection = self._connect(device)
        try:
            # Many lab logins land in unprivileged exec (e.g. `Sw3>`), where
            # `configure` is rejected and netmiko times out waiting for the
            # `(config)#` prompt. Enter enable mode first when needed; enable()
            # uses device.enable_password as the secret when set, and works with
            # no secret when the device doesn't require one. Platforms without an
            # enable mode (e.g. Junos) report check_enable_mode() True and skip it.
            if hasattr(connection, "check_enable_mode") and not connection.check_enable_mode():
                connection.enable()
            return str(connection.send_config_set(commands))
        finally:
            connection.disconnect()

    def _connect(self, device: Device) -> Any:
        try:
            from netmiko import ConnectHandler
        except ImportError as exc:
            raise RuntimeError("Install netmiko to use ssh transport.") from exc

        params: dict[str, Any] = {
            "device_type": _netmiko_device_type(device.platform),
            "host": device.host,
            "username": device.username,
            "password": device.password,
            "port": device.port,
        }
        if device.enable_password:
            params["secret"] = device.enable_password
        params.update(device.extras)
        return ConnectHandler(**params)


def driver_for_device(device: Device) -> NetworkDriver:
    transport = device.transport.lower()
    if transport == "mock":
        return MockNetworkDriver()
    if transport == "ssh":
        return NetmikoDriver()
    raise ValueError(f"Unsupported transport {device.transport!r} for {device.name}.")


def _netmiko_device_type(platform: str) -> str:
    platform = platform.lower()
    aliases = {
        "ios": "cisco_ios",
        "cisco_xe": "cisco_ios",
        "eos": "arista_eos",
        "nxos": "cisco_nxos",
        "junos": "juniper_junos",
        "frr": "linux",
        "linux_frr": "linux",
    }
    return aliases.get(platform, platform)


def _mock_version(device: Device) -> str:
    return (
        f"{device.name}# show version\n"
        f"Packet Coders virtual lab image\n"
        f"Platform: {device.platform}\n"
        "Uptime: 2 days, 4 hours\n"
        "Control plane: healthy"
    )


def _mock_interfaces(device: Device) -> str:
    return (
        f"{device.name}# show ip interface brief\n"
        "Interface              IP-Address      OK? Method Status                Protocol\n"
        "Loopback0              10.255.0.1      YES manual up                    up\n"
        "Ethernet1              10.0.12.1       YES manual up                    up\n"
        "Ethernet2              10.0.13.1       YES manual up                    up"
    )


def _mock_routes(device: Device) -> str:
    return (
        f"{device.name}# show ip route summary\n"
        "Route Source    Networks    Subnets     Replicates  Overhead\n"
        "connected       3           3           0           384\n"
        "ospf            6           6           0           768\n"
        "bgp             4           4           0           512"
    )


def _mock_ospf(device: Device) -> str:
    return (
        f"{device.name}# show ip ospf neighbor\n"
        "Neighbor ID     Pri   State           Dead Time   Address         Interface\n"
        "10.255.0.2        1   FULL/DR         00:00:31    10.0.12.2       Ethernet1\n"
        "10.255.0.3        1   FULL/BDR        00:00:34    10.0.13.3       Ethernet2"
    )


def _mock_bgp(device: Device) -> str:
    return (
        f"{device.name}# show ip bgp summary\n"
        "BGP router identifier 10.255.0.1, local AS number 65001\n"
        "Neighbor        V    AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd\n"
        "10.0.12.2       4 65002     241     238       12    0    0 02:04:19        4\n"
        "10.0.13.3       4 65003     229     231       12    0    0 02:03:55        4"
    )
