from __future__ import annotations

import asyncio

from fastmcp import Client

from packet_coders_mcp.server import get_lab_service, mcp


def test_mcp_server_lists_devices() -> None:
    async def run() -> None:
        get_lab_service.cache_clear()
        async with Client(mcp) as client:
            result = await client.call_tool("list_lab_devices", {})

        assert result.data["devices"]["r1"]["transport"] == "mock"

    asyncio.run(run())
