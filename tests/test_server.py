from __future__ import annotations

import asyncio
import importlib

import pytest
from fastmcp import Client

import packet_coders_mcp.server as server
from packet_coders_mcp.server import get_lab_service, mcp


def test_mcp_server_lists_devices() -> None:
    async def run() -> None:
        get_lab_service.cache_clear()
        async with Client(mcp) as client:
            result = await client.call_tool("list_lab_devices", {})

        assert result.data["devices"]["r1"]["transport"] == "mock"

    asyncio.run(run())


def _server_tool_names() -> set[str]:
    async def run() -> set[str]:
        async with Client(server.mcp) as client:
            tools = await client.list_tools()
        return {tool.name for tool in tools}

    return asyncio.run(run())


@pytest.fixture
def _restore_server() -> object:
    """Reload the server module back to its default (writes-disabled) state."""
    yield
    importlib.reload(server)


def test_write_tool_exposed_by_default(
    monkeypatch: pytest.MonkeyPatch, _restore_server: object
) -> None:
    # Default (no env): configure_device is exposed, but still behind the confirmation gate.
    monkeypatch.delenv("PACKET_CODERS_ALLOW_WRITES", raising=False)
    importlib.reload(server)

    names = _server_tool_names()

    assert "configure_device" in names
    assert "list_lab_devices" in names


def test_write_tool_hidden_in_readonly_mode(
    monkeypatch: pytest.MonkeyPatch, _restore_server: object
) -> None:
    monkeypatch.setenv("PACKET_CODERS_ALLOW_WRITES", "false")
    importlib.reload(server)

    names = _server_tool_names()

    assert "configure_device" not in names
    assert "list_lab_devices" in names
