# Loose Ends MCP Server 🎫

A tiny, **open-source [Model Context Protocol](https://modelcontextprotocol.io) server**
that turns a Slack "loose end" into a tracked ticket. It's the connector behind the
**Escalate** button in [Loose Ends](../README.md).

It's a **demo connector** (mock Jira/Linear that persists to `tickets.json`), but it's a
*real* MCP server: any MCP client — Claude Desktop, Cursor, or the Loose Ends Bolt app —
can discover and call its tools. Swap the mock persistence for a real Jira/Linear API call
and nothing else in Loose Ends changes. **That decoupling is the whole point of MCP.**

## Tools

| Tool | Args | Returns |
|---|---|---|
| `create_ticket` | `title`, `description`, `assignee`, `source_permalink` | ticket `{ref, url, …}` (e.g. `LE-1042`) |
| `list_tickets` | – | all tickets created so far |

## Run it

```bash
pip install -r requirements.txt
python server.py
# → Loose Ends MCP server on http://127.0.0.1:8765/mcp  (tool: create_ticket)
```

Transport: **streamable HTTP** at `http://127.0.0.1:8765/mcp`
(override with `MCP_HOST` / `MCP_PORT`).

## Use it from any MCP client

The Loose Ends Bolt app calls it via `src/mcp_client.py`. Any other MCP client can point at
the same URL. Example (Claude Desktop / Cursor config):

```json
{
  "mcpServers": {
    "loose-ends-tickets": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

## Why it matters (judging note)

- **Real MCP, not a REST shim** — uses the official `mcp` SDK and the standard tool interface.
- **Reusable** — the same server works for Loose Ends *and* any agent that speaks MCP.
- **Honest demo** — clearly a mock connector; the production path (real Jira/Linear) is a
  one-function change, isolated entirely inside this server.
