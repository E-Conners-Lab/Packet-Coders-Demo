#!/usr/bin/env python3
"""Operator tool to strip and rebuild the Packet Coders demo lab.

Drives the same LabService the MCP server wraps, against the live inventory
(PACKET_CODERS_INVENTORY, default ``inventory.local.yaml``). The topology is
discovered live from LLDP on every run, so the IP/AS plan is derived from the
real wiring rather than hardcoded.

Usage:
    PACKET_CODERS_INVENTORY=inventory.local.yaml uv run python scripts/lab.py <command>

Commands:
    verify        Show current OSPF / eBGP state on every switch (read-only).
    plan          Discover via LLDP and PRINT the strip + build config, send nothing.
    strip         Remove OSPF, eBGP, routed-port IPs, and loopbacks (mgmt untouched).
    build         Discover via LLDP, then push OSPF area 0 + eBGP full mesh.
    prefer-ebgp   Set 'distance bgp 20 200 200' so eBGP wins the RIB over OSPF.
    rebuild       strip, let LLDP settle, then build.

Addressing (derived from the switch number N in each device name):
    loopback   10.255.0.N/32              router-id, and AS 6500N
    link A<->B 10.<min><max>.<min><max>.0/24, host octet = the switch's own number
"""
from __future__ import annotations

import os
import re
import sys
import time

from packet_coders_mcp.inventory import load_inventory
from packet_coders_mcp.lab import LabService

ASN_BASE = 65000
DATA_PORTS = ("Ethernet1", "Ethernet2", "Ethernet3")  # mgmt (Management1) is never touched


def switch_num(name: str) -> int:
    match = re.search(r"(\d+)$", name)
    if not match:
        raise ValueError(f"Cannot derive a switch number from {name!r}")
    return int(match.group(1))


def link_prefix(a: int, b: int) -> str:
    lo, hi = sorted((a, b))
    return f"10.{lo}{hi}.{lo}{hi}"


def lab_service() -> tuple[LabService, list[str]]:
    inv_path = os.environ.get("PACKET_CODERS_INVENTORY", "inventory.local.yaml")
    inventory = load_inventory(inv_path)
    return LabService(inventory), sorted(inventory.devices)


def discover(lab: LabService, devices: list[str]) -> dict[str, dict[str, str]]:
    """Return {device: {local_port: remote_device}} parsed from live LLDP."""
    known = set(devices)
    adjacency: dict[str, dict[str, str]] = {}
    for device in devices:
        output = lab.send_command(device, "show lldp neighbors")["output"]
        local: dict[str, str] = {}
        for line in output.splitlines():
            tokens = line.split()
            if len(tokens) >= 3 and re.match(r"Et\d", tokens[0]):
                remote = tokens[1].upper()
                if remote in known:
                    local[tokens[0].replace("Et", "Ethernet")] = remote
        adjacency[device] = local
    return adjacency


def discover_stable(lab: LabService, devices: list[str], timeout: int = 90) -> dict[str, dict[str, str]]:
    """Poll LLDP until every link is seen from both ends (handles post-strip relearn)."""
    deadline = time.time() + timeout
    while True:
        adjacency = discover(lab, devices)
        bidirectional = all(
            device in adjacency.get(remote, {}).values()
            for device, links in adjacency.items()
            for remote in links.values()
        )
        if bidirectional and any(adjacency.values()):
            return adjacency
        if time.time() > deadline:
            print(f"  ! LLDP not fully converged after {timeout}s; proceeding with what was found")
            return adjacency
        print("  ... waiting for LLDP to populate")
        time.sleep(10)


def build_cfg(device: str, links: dict[str, str]) -> list[str]:
    n = switch_num(device)
    cfg = ["ip routing"]
    subnets: list[str] = []
    for port, remote in sorted(links.items()):
        subnet = link_prefix(n, switch_num(remote))
        cfg += [f"interface {port}", "no switchport", f"ip address {subnet}.{n}/24"]
        subnets.append(subnet)
    cfg += ["interface Loopback0", f"ip address 10.255.0.{n}/32"]
    cfg += ["router ospf 1", f"router-id 10.255.0.{n}"]
    cfg += [f"network {subnet}.0/24 area 0" for subnet in sorted(subnets)]
    cfg.append(f"network 10.255.0.{n}/32 area 0")
    cfg += [f"router bgp {ASN_BASE + n}", f"router-id 10.255.0.{n}"]
    for port, remote in sorted(links.items()):
        rn = switch_num(remote)
        cfg.append(f"neighbor {link_prefix(n, rn)}.{rn} remote-as {ASN_BASE + rn}")
    cfg.append(f"network 10.255.0.{n}/32")
    return cfg


def strip_cfg(device: str) -> list[str]:
    n = switch_num(device)
    cfg = [f"no router bgp {ASN_BASE + n}", "no router ospf 1"]
    cfg += [f"default interface {port}" for port in DATA_PORTS]
    cfg.append("no interface Loopback0")
    return cfg


def prefer_ebgp_cfg(device: str) -> list[str]:
    return [f"router bgp {ASN_BASE + switch_num(device)}", "distance bgp 20 200 200"]


def established_bgp(output: str) -> int:
    """Count Established eBGP sessions in a 'show ip bgp summary' (peer line ends in PfxRcd)."""
    count = 0
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0].count(".") == 3 and fields[-1].isdigit():
            count += 1
    return count


def push(lab: LabService, device: str, cfg: list[str]) -> None:
    result = lab.configure_device(device, cfg, dry_run=False, confirm=True)
    print(f"  {device}: {'OK' if not result.get('dry_run') else 'DRY-RUN (not applied)'}")


def cmd_verify(lab: LabService, devices: list[str]) -> None:
    print("== VERIFY ==")
    adjacency = discover(lab, devices)
    for device in devices:
        want = len(adjacency[device])
        ospf = lab.get_ospf_neighbors(device)["neighbor_count_hint"]
        bgp = established_bgp(lab.get_bgp_summary(device)["output"])
        print(f"  {device}: OSPF {ospf}/{want} neighbors | eBGP {bgp}/{want} established")
    others = [d for d in devices if d != devices[0]]
    if others:
        target = switch_num(others[0])
        route = lab.send_command(devices[0], f"show ip route 10.255.0.{target}")["output"]
        source = "eBGP (B E)" if re.search(r"^\s*B E\s", route, re.M) else (
            "OSPF (O)" if re.search(r"^\s*O\s", route, re.M) else "not present")
        print(f"  forwarding: {devices[0]} reaches 10.255.0.{target} via {source}")


def cmd_plan(lab: LabService, devices: list[str]) -> None:
    print("== PLAN (no config is sent) ==")
    adjacency = discover_stable(lab, devices)
    for device in devices:
        wiring = ", ".join(f"{p.replace('Ethernet', 'Et')}->{r}" for p, r in sorted(adjacency[device].items()))
        print(f"\n# {device}  ({wiring})")
        print("#  strip:")
        for line in strip_cfg(device):
            print(f"    {line}")
        print("#  build:")
        for line in build_cfg(device, adjacency[device]):
            print(f"    {line}")


def cmd_strip(lab: LabService, devices: list[str]) -> None:
    print("== STRIP ==")
    for device in devices:
        push(lab, device, strip_cfg(device))
    print("Removed OSPF, eBGP, routed-port IPs, and loopbacks. Management plane untouched.")


def cmd_build(lab: LabService, devices: list[str]) -> None:
    print("== DISCOVER (LLDP) ==")
    adjacency = discover_stable(lab, devices)
    for device in devices:
        wiring = ", ".join(f"{p.replace('Ethernet', 'Et')}->{r}" for p, r in sorted(adjacency[device].items()))
        print(f"  {device}: {wiring}")
    print("== BUILD (OSPF area 0 + eBGP full mesh) ==")
    for device in devices:
        push(lab, device, build_cfg(device, adjacency[device]))
    print("== WAIT FOR CONVERGENCE ==")
    deadline = time.time() + 120
    while True:
        done = True
        rows = []
        for device in devices:
            want = len(adjacency[device])
            ospf = lab.get_ospf_neighbors(device)["neighbor_count_hint"]
            bgp = established_bgp(lab.get_bgp_summary(device)["output"])
            rows.append(f"{device} OSPF {ospf}/{want} BGP {bgp}/{want}")
            if ospf < want or bgp < want:
                done = False
        print("  " + " | ".join(rows))
        if done or time.time() > deadline:
            break
        time.sleep(10)


def cmd_prefer(lab: LabService, devices: list[str]) -> None:
    print("== PREFER eBGP (distance bgp 20) ==")
    for device in devices:
        push(lab, device, prefer_ebgp_cfg(device))
    print("eBGP external distance set to 20; loopbacks now install via eBGP (B E).")


def cmd_rebuild(lab: LabService, devices: list[str]) -> None:
    cmd_strip(lab, devices)
    print("\n... letting LLDP and interfaces settle (20s) ...\n")
    time.sleep(20)
    cmd_build(lab, devices)


COMMANDS = {
    "verify": cmd_verify,
    "plan": cmd_plan,
    "strip": cmd_strip,
    "build": cmd_build,
    "prefer-ebgp": cmd_prefer,
    "rebuild": cmd_rebuild,
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("Commands:", ", ".join(COMMANDS))
        return 1
    lab, devices = lab_service()
    print(f"Inventory: {len(devices)} switches -> {', '.join(devices)}\n")
    COMMANDS[sys.argv[1]](lab, devices)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
