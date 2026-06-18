from __future__ import annotations

import re

DANGEROUS_PATTERNS = (
    r"^\s*reload\b",
    r"^\s*erase\b",
    r"^\s*delete\b",
    r"^\s*format\b",
    r"^\s*write\s+erase\b",
    r"^\s*request\s+system\s+reboot\b",
    r"^\s*request\s+system\s+zeroize\b",
)

CONFIG_MODE_PATTERNS = (
    r"^\s*configure\s+terminal\b",
    r"^\s*conf\s+t\b",
    r"^\s*end\s*$",
)


def assert_safe_show_command(command: str) -> None:
    normalized = command.strip().lower()
    if not normalized:
        raise ValueError("Command cannot be empty.")
    if not (
        normalized.startswith("show ")
        or normalized.startswith("display ")
        or normalized.startswith("vtysh -c \"show ")
    ):
        raise ValueError("send_command only allows read-only show/display commands.")
    assert_not_dangerous(command)


def assert_safe_config_lines(commands: list[str]) -> None:
    if not commands:
        raise ValueError("At least one config line is required.")
    for command in commands:
        assert_not_dangerous(command)
        for pattern in CONFIG_MODE_PATTERNS:
            if re.search(pattern, command, flags=re.IGNORECASE):
                raise ValueError(
                    "Pass only config lines. Do not include configure terminal, conf t, or end."
                )


def assert_not_dangerous(command: str) -> None:
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, flags=re.IGNORECASE):
            raise ValueError(f"Blocked dangerous command: {command!r}")
