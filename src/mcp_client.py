"""MCP client wrapper: lets the Bolt app call the Loose Ends MCP server.

Connects over streamable HTTP, calls the `create_ticket` tool, and returns the
ticket dict. Fully resilient — any failure (server down, timeout, bad payload)
returns None instead of raising, so Escalate degrades gracefully.
"""
import asyncio
import json
import logging
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

log = logging.getLogger("looseends.mcp")

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:8765/mcp")


async def _call_tool(name: str, args: dict, timeout: float):
    async def _inner():
        async with streamablehttp_client(MCP_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(name, args)

    return await asyncio.wait_for(_inner(), timeout=timeout)


def _extract(result) -> dict | None:
    if result is None or getattr(result, "isError", False):
        return None
    sc = getattr(result, "structuredContent", None)
    if isinstance(sc, dict):
        if "ref" in sc:
            return sc
        inner = sc.get("result")
        if isinstance(inner, dict) and "ref" in inner:
            return inner
    for c in getattr(result, "content", []) or []:
        txt = getattr(c, "text", None)
        if txt:
            try:
                d = json.loads(txt)
                if isinstance(d, dict) and "ref" in d:
                    return d
            except json.JSONDecodeError:
                continue
    return None


def create_ticket(
    title: str,
    description: str = "",
    assignee: str = "",
    source_permalink: str = "",
    timeout: float = 12.0,
) -> dict | None:
    """Create a ticket via the MCP server. Returns the ticket dict or None on failure."""
    args = {
        "title": title,
        "description": description,
        "assignee": assignee,
        "source_permalink": source_permalink,
    }
    try:
        result = asyncio.run(_call_tool("create_ticket", args, timeout))
    except Exception as e:  # noqa: BLE001 — Escalate must never crash the app
        log.warning("MCP create_ticket failed: %s", e)
        return None
    ticket = _extract(result)
    if ticket is None:
        log.warning("MCP create_ticket returned no usable ticket")
    return ticket
