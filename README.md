# Loose Ends 🪢

**The accountability agent for Slack.** It catches the promises people make in chat
("I'll send the deck Friday") and the questions that scroll away unanswered — then
privately nudges the right person, with one click to **Done / Snooze / Reassign /
Escalate-to-ticket**.

Built solo for the **Slack Agent Builder Challenge**.

---

## The problem

Work doesn't get dropped because people don't care. It gets dropped because **the promise
lives in a chat message, and chat scrolls away.** Nobody re-reads Tuesday's thread. The
deck doesn't get sent, the question never gets answered, and it surfaces a week later as
"wait, I thought you had that?"

Every team has a task tracker. Almost nothing that gets promised in Slack ever reaches it.

## The solution

Loose Ends watches channel conversations and detects two things:

1. **Commitments** — "I'll send the Q3 deck by EOD", "on it, will fix tonight"
2. **Unanswered questions** — "who's handling the prod deploy?" with no reply

It stores each as a *loose end*, then a scheduler **privately DMs the owner** when a
commitment goes overdue or a question goes stale. Never a public call-out. Every nudge is
a Block Kit card with real actions — including **Escalate**, which creates a tracked
ticket through an open-source **MCP server**.

**The extractor is deliberately conservative.** "lol same" and "the build is green" are
ignored. False positives are worse than misses — an agent that nags you about nothing gets
muted on day one.

---

## How it uses the three platform pillars

| Pillar | How Loose Ends uses it |
|---|---|
| **Slack AI / LLM** | An LLM extractor (`src/llm.py`) classifies every message into commitment / question / noise with a confidence score, and writes the grounded `/ask` answers. |
| **Real-Time Search (RTS)** | `/looseends ask "what did I commit to this week?"` calls **`assistant.search.context`** to ground the answer in what was *actually said* in the workspace, with permalink citations. |
| **MCP** | **Escalate** calls our own standalone [MCP server](./mcp-server) (`create_ticket` tool) to turn a forgotten Slack promise into a tracked ticket. Open-sourced in this repo. |

---

## Architecture

```
message events → extractor (LLM) → SQLite → scheduler → Block Kit nudge → actions
                                                 ↓
                          App Home dashboard · /looseends ask (RTS) · Escalate (MCP)
```

```
        ┌─────────────────────────────────────────────┐
        │              SLACK WORKSPACE                 │
        │  channels · threads · App Home · slash cmds  │
        └───────────────┬───────────────▲──────────────┘
        message events  │               │  nudge cards / dashboard / replies
                        ▼               │
        ┌───────────────────────────────┴──────────────┐
        │           LOOSE ENDS (Bolt for Python)        │
        │  1. Extractor  ── LLM ──► {type, owner, due}  │
        │  2. Store (SQLite: loose_ends)                │
        │  3. Scheduler (APScheduler) ─► overdue/stale  │
        │  4. Actions: Done / Snooze / Reassign / Escalate
        │  5. App Home dashboard                        │
        │  6. /looseends ask ─► RTS ─► grounded answer  │
        └───────┬───────────────────────────┬───────────┘
                │ RTS API                    │ MCP
                ▼                            ▼
     ┌──────────────────────┐    ┌────────────────────────────┐
     │ assistant.search      │    │  Loose Ends MCP Server      │
     │ .context (citations)  │    │  tool: create_ticket()      │
     └──────────────────────┘    └────────────────────────────┘
```

**Failure is designed in.** Every layer degrades instead of breaking:
RTS unavailable → `/ask` answers from the DB *and says so*. LLM down → a plain tracked
list. MCP server down → Escalate reports it and the item stays open. The core loop
(detect → store → nudge → act) needs only the bot token.

### Files

| File | Role |
|---|---|
| `src/app.py` | Bolt app: events, capture, buttons, modals, slash command |
| `src/llm.py` | LLM extractor + grounded answer writer |
| `src/duedate.py` | "friday" / "by EOD" / "tonight" → epoch ms |
| `src/db.py` | SQLite storage (stdlib `sqlite3`) |
| `src/scheduler.py` | APScheduler nudge engine (overdue + stale) |
| `src/nudge.py` | State-aware Block Kit card renderer |
| `src/home.py` | App Home dashboard |
| `src/rts.py` | Real-Time Search client (`assistant.search.context`) |
| `src/ask.py` | `/looseends ask` — grounded, cited answers |
| `src/mcp_client.py` | Resilient MCP client for Escalate |
| `mcp-server/` | **Standalone open-source MCP server** (FastMCP) |

---

## Quick start

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows; else .venv/bin/pip
cp .env.example .env                                # fill in your tokens
```

Two processes:

```bash
# 1. the MCP ticket server
cd mcp-server && ../.venv/Scripts/python.exe -u server.py    # → 127.0.0.1:8765

# 2. the Slack app (Socket Mode — no public URL needed)
.venv/Scripts/python.exe -u -m src.app
```

Invite the bot to a channel, then say something you'd regret forgetting.

### Slack app configuration

**Bot scopes:** `app_mentions:read`, `channels:history`, `groups:history`, `chat:write`,
`commands`, `im:write`, `im:history`, `users:read`, `reactions:write`
**User scope (for RTS):** `search:read.public`
**Events:** `message.channels`, `message.groups`, `app_mention`, `app_home_opened`
**Also:** Socket Mode on, Interactivity on, App Home **Home tab + Messages tab** enabled
(the Messages tab is required — without it the bot can't DM nudges), `/looseends` command.

> **On the RTS user token:** `/looseends ask` needs a `xoxp-` **user** token. Bot-token RTS
> calls require an `action_token` that Slack only mints inside message events, so a slash
> command can't use one. Add `search:read.public` under **User** Token Scopes, reinstall,
> and set `SLACK_USER_TOKEN`. Leave it unset and `/ask` transparently falls back to DB-only.

### Commands

| Command | Does |
|---|---|
| `/looseends` | Your open loose ends |
| `/looseends ask <question>` | Grounded, cited answer (RTS + your tracked items) |
| `/looseends check` | Run the overdue/stale check right now |
| `/looseends help` | What I can do |

### Scripts

```bash
scripts/seed_demo.py      # reset to a clean, known demo state
scripts/rts_smoke.py      # verify the RTS path end to end
scripts/extract_smoke.py  # extractor accuracy check
scripts/db_smoke.py       # storage smoke test
scripts/list_ends.py      # dump tracked loose ends
scripts/make_logo.py      # re-render the app icon (needs `pillow`)
```

## Brand

The mark is a loop of thread that never got tied off, trailing to a frayed end —
`assets/logo.svg`, rendered to `assets/logo-512.png` for the Slack app icon.

---

## Data handling & security

Be able to answer these before you install this anywhere real.

**What leaves the workspace.** Every message posted in a channel the bot is invited to
(longer than a few characters, excluding bot messages) is sent to an **LLM gateway** —
by default [DGrid](https://dgrid.ai), an OpenAI-compatible endpoint — for classification.
That is a third party receiving your team's conversations. `src/llm.py` is a deliberately
thin wrapper: point `DGRID_BASE_URL` at any OpenAI-compatible endpoint, including a
self-hosted or in-VPC model, and nothing else changes. The bot is only ever in the channels
you invite it to.

**What's stored.** Loose ends live in a local SQLite file: the summary, owner, channel,
message timestamp, due date, and status. Message bodies are not stored — only the short
summary the extractor produces. Nothing is sent anywhere except Slack, the LLM gateway,
and your MCP connector.

**Real-Time Search runs as the asking user.** `/looseends ask` uses a `xoxp-` user token
scoped to `search:read.public`, so it can only ever surface messages that user could
already read. It cannot widen anyone's access.

**The MCP server has no authentication.** It binds `127.0.0.1` and is meant to run beside
the app. If you change `MCP_HOST`, anyone who can reach the port can create tickets — put
real auth in front of it first. It warns you on startup if you bind it off-loopback.

**Nudges are private.** The agent DMs the owner. It never posts a public call-out, and it
never @-mentions someone to shame them into acting.

**Known limits.** A crafted message could try to talk the extractor into creating a bogus
loose end, or steer an `/ask` answer — the blast radius is a wrong card, and every action
still needs a human to click. There's no rate limiting: an LLM call fires per qualifying
message, so a busy channel costs money.

---

## What's next

- **Real connectors.** The MCP server ships a mock ticket store; the `create_ticket` tool
  contract is already the right shape for Jira/Linear. Swapping it doesn't touch the Slack app.
- **Learning the owner's rhythm** — nudge when someone is actually free, not at 2am.
- **Marketplace listing** as a drop-in accountability layer for any workspace.

## Stack

Bolt for Python (Socket Mode) · LLM extraction via an OpenAI-compatible gateway ·
stdlib SQLite · APScheduler · Slack Real-Time Search · a standalone open-source
[MCP server](./mcp-server).

See [`PROJECT_SPEC.md`](./PROJECT_SPEC.md) for the data model and scopes,
[`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md) for the demo run-of-show.
