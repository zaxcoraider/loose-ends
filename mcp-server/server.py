"""Loose Ends — MCP Server (open-source demo connector).

A tiny, standalone Model Context Protocol server exposing a single tool,
`create_ticket`, that mocks a Jira/Linear ticket creation. Any MCP client
(Claude Desktop, Cursor, or the Loose Ends Bolt app) can call it.

Tickets are persisted to tickets.json so the demo shows a growing list.

Run (streamable HTTP, default http://127.0.0.1:8765/mcp):
    python server.py

This is a DEMO connector — swap the persistence for a real Jira/Linear API
call and it becomes production-ready. That swap is the whole point of MCP:
the Loose Ends app never changes, only this connector does.
"""
import json
import os
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8765"))
TICKETS_FILE = os.path.join(os.path.dirname(__file__), "tickets.json")
FIRST_TICKET_NUM = 1

# Base URL of the real tracker this connector writes to. Unset in the demo, because
# this store is local: we return no URL rather than a link to a host that doesn't exist.
# Point it at a real Jira/Linear instance and refs become clickable everywhere.
TICKET_BASE_URL = os.environ.get("TICKET_BASE_URL", "").rstrip("/")

mcp = FastMCP("loose-ends-tickets", host=HOST, port=PORT)


def _load() -> dict:
    if os.path.exists(TICKETS_FILE):
        try:
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"next_num": FIRST_TICKET_NUM, "tickets": []}


def _save(state: dict) -> None:
    with open(TICKETS_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


@mcp.tool()
def create_ticket(
    title: str,
    description: str = "",
    assignee: str = "",
    source_permalink: str = "",
) -> dict:
    """Create a tracking ticket from a Slack loose end (mock Jira/Linear connector).

    Args:
        title: Short ticket title (e.g. the loose-end summary).
        description: Longer context for the ticket body.
        assignee: Who the ticket is assigned to (Slack user id or name).
        source_permalink: Link back to the originating Slack message.

    Returns:
        A dict with the ticket ref, url, and stored fields.
    """
    state = _load()
    num = state["next_num"]
    ref = f"LE-{num}"
    ticket = {
        "ref": ref,
        "url": f"{TICKET_BASE_URL}/{ref}" if TICKET_BASE_URL else None,
        "title": title,
        "description": description,
        "assignee": assignee,
        "source_permalink": source_permalink,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "open",
    }
    state["tickets"].append(ticket)
    state["next_num"] = num + 1
    _save(state)
    return ticket


@mcp.tool()
def list_tickets() -> list[dict]:
    """List every ticket this connector has created."""
    return _load()["tickets"]


if __name__ == "__main__":
    print(f"Loose Ends MCP server on http://{HOST}:{PORT}/mcp  (tool: create_ticket)")
    if HOST not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"  !! WARNING: bound to {HOST}, not loopback.\n"
            "  !! This server has NO AUTHENTICATION — anyone who can reach this port can\n"
            "  !! create tickets. Keep it on 127.0.0.1, or put a real auth layer in front\n"
            "  !! of it before exposing it to a network."
        )
    mcp.run(transport="streamable-http")
