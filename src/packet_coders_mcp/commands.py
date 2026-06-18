from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformCommands:
    health: tuple[str, ...]
    ospf_neighbors: str
    bgp_summary: str


COMMANDS: dict[str, PlatformCommands] = {
    "cisco_ios": PlatformCommands(
        health=("show version", "show ip interface brief", "show ip route summary"),
        ospf_neighbors="show ip ospf neighbor",
        bgp_summary="show ip bgp summary",
    ),
    "cisco_xe": PlatformCommands(
        health=("show version", "show ip interface brief", "show ip route summary"),
        ospf_neighbors="show ip ospf neighbor",
        bgp_summary="show ip bgp summary",
    ),
    "ios": PlatformCommands(
        health=("show version", "show ip interface brief", "show ip route summary"),
        ospf_neighbors="show ip ospf neighbor",
        bgp_summary="show ip bgp summary",
    ),
    "arista_eos": PlatformCommands(
        health=("show version", "show ip interface brief", "show ip route summary"),
        ospf_neighbors="show ip ospf neighbor",
        bgp_summary="show ip bgp summary",
    ),
    "eos": PlatformCommands(
        health=("show version", "show ip interface brief", "show ip route summary"),
        ospf_neighbors="show ip ospf neighbor",
        bgp_summary="show ip bgp summary",
    ),
    "cisco_nxos": PlatformCommands(
        health=("show version", "show ip interface brief", "show ip route summary"),
        ospf_neighbors="show ip ospf neighbors",
        bgp_summary="show bgp ipv4 unicast summary",
    ),
    "nxos": PlatformCommands(
        health=("show version", "show ip interface brief", "show ip route summary"),
        ospf_neighbors="show ip ospf neighbors",
        bgp_summary="show bgp ipv4 unicast summary",
    ),
    "junos": PlatformCommands(
        health=("show version", "show interfaces terse", "show route summary"),
        ospf_neighbors="show ospf neighbor",
        bgp_summary="show bgp summary",
    ),
    "juniper_junos": PlatformCommands(
        health=("show version", "show interfaces terse", "show route summary"),
        ospf_neighbors="show ospf neighbor",
        bgp_summary="show bgp summary",
    ),
    "frr": PlatformCommands(
        health=(
            'vtysh -c "show version"',
            'vtysh -c "show interface brief"',
            'vtysh -c "show ip route summary"',
        ),
        ospf_neighbors='vtysh -c "show ip ospf neighbor"',
        bgp_summary='vtysh -c "show ip bgp summary"',
    ),
    "linux_frr": PlatformCommands(
        health=(
            'vtysh -c "show version"',
            'vtysh -c "show interface brief"',
            'vtysh -c "show ip route summary"',
        ),
        ospf_neighbors='vtysh -c "show ip ospf neighbor"',
        bgp_summary='vtysh -c "show ip bgp summary"',
    ),
}


def commands_for_platform(platform: str) -> PlatformCommands:
    """Return platform command choices, falling back to IOS-like commands."""
    return COMMANDS.get(platform.lower(), COMMANDS["cisco_ios"])
