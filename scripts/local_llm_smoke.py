"""Read-only end-to-end smoke test: a local LLM driving the MCP lab tools.

Connects to the Packet Coders MCP server in-process, exposes only the read-only
tools to a local OpenAI-compatible model (Ollama or vLLM), runs the tool-calling
loop, and lets the model answer a question about the live lab.

`configure_device` is intentionally withheld so this test can never write to a
device. Backend URL, model, and inventory come from the environment so no host
or credential is baked into the file.

Usage:
    LLM_BASE_URL=http://<host>:11434/v1 \
    LLM_MODEL=qwen3.6:35b-32k \
    PACKET_CODERS_INVENTORY=./inventory.local.yaml \
    uv run --project . python scripts/local_llm_smoke.py "Are SW1's OSPF neighbors all FULL?"
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys

import httpx
from fastmcp import Client

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_reasoning(text: str) -> str:
    """Remove inline <think>...</think> blocks some backends (e.g. vLLM) include."""
    return _THINK_RE.sub("", text or "").strip()


READ_ONLY_TOOLS = {
    "list_lab_devices",
    "send_command",
    "run_health_check",
    "get_ospf_neighbors",
    "get_bgp_summary",
}

SYSTEM_PROMPT = (
    "You are a network assistant for a small lab. Use the provided tools to gather "
    "facts before answering. Only use the tools given to you. Be concise and cite the "
    "device names and numbers you observed."
)

MAX_STEPS = 6


def _require_env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _tool_result_to_text(result: object) -> str:
    """Serialize a CallToolResult into something the model can read."""
    for attr in ("data", "structured_content"):
        payload = getattr(result, attr, None)
        if payload is not None:
            return json.dumps(payload, default=str)
    content = getattr(result, "content", None)
    if content:
        parts = [getattr(block, "text", str(block)) for block in content]
        return "\n".join(parts)
    return json.dumps(result, default=str)


async def run(prompt: str) -> int:
    base_url = _require_env("LLM_BASE_URL").rstrip("/")
    model = _require_env("LLM_MODEL")
    # Force the MCP server onto the chosen inventory before its lazy singleton builds.
    os.environ.setdefault("PACKET_CODERS_INVENTORY", "./inventory.local.yaml")

    from packet_coders_mcp.server import mcp  # imported after env is set

    async with Client(mcp) as client:
        all_tools = await client.list_tools()
        tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema or {"type": "object", "properties": {}},
                },
            }
            for t in all_tools
            if t.name in READ_ONLY_TOOLS
        ]
        print(f"Exposing {len(tools)} read-only tools to {model}: "
              f"{', '.join(sorted(t['function']['name'] for t in tools))}\n")

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        async with httpx.AsyncClient(timeout=300) as http:
            for step in range(1, MAX_STEPS + 1):
                resp = await http.post(
                    f"{base_url}/chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        "tools": tools,
                        "tool_choice": "auto",
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]
                tool_calls = msg.get("tool_calls") or []

                if not tool_calls:
                    print(f"=== final answer (after {step - 1} tool call round(s)) ===")
                    print(_strip_reasoning(msg.get("content", "")))
                    return 0

                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.get("content") or "",
                        "tool_calls": tool_calls,
                    }
                )
                for tc in tool_calls:
                    name = tc["function"]["name"]
                    raw_args = tc["function"].get("arguments") or "{}"
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    if name not in READ_ONLY_TOOLS:
                        text = f"ERROR: tool {name!r} is not permitted in this read-only test."
                    else:
                        print(f"  [step {step}] -> {name}({json.dumps(args)})")
                        result = await client.call_tool(name, args)
                        text = _tool_result_to_text(result)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": text})

        print(f"Stopped after {MAX_STEPS} tool rounds without a final answer.")
        return 1


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('Usage: local_llm_smoke.py "<question for the lab>"')
    raise SystemExit(asyncio.run(run(sys.argv[1])))


if __name__ == "__main__":
    main()
