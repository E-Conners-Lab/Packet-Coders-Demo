# Suggested Webinar Flow

1. Start with `configs/inventory.mock.yaml` and list devices.
2. Show `server.py` and how `@mcp.tool` turns Python functions into MCP tools.
3. Run `get_ospf_neighbors` and `get_bgp_summary` against the mock lab.
4. Switch `PACKET_CODERS_INVENTORY` to the EVE-NG inventory (the four-switch mesh in
   [topology.md](topology.md)).
5. Run the same tools against the real lab and show the full-mesh adjacencies.
6. Demonstrate `configure_device` from a host that confirms tool calls (Claude Desktop / Code),
   with the server started `PACKET_CODERS_ALLOW_WRITES=true`: dry-run first, then approve the real
   change — add and remove a demo loopback, verifying it appears in the neighbors' routing tables
   (as an `O` or `B` route, depending on whether you advertise it into OSPF or BGP). Keep the
   Open WebUI / Ollama path write-disabled so the auto-executing agent can never push config.
7. Optional: repeat the demo driven by a local Qwen3 model to show the same tools with no
   cloud API.
