# Loose Ends — Project Spec

## Architecture

```
        ┌─────────────────────────────────────────────┐
        │              SLACK WORKSPACE                 │
        │  channels · threads · App Home · slash cmds  │
        └───────────────┬───────────────▲──────────────┘
        message events  │               │  nudge cards / dashboard / replies
                        ▼               │
        ┌───────────────────────────────┴──────────────┐
        │           LOOSE ENDS (Bolt for Python)        │
        │                                               │
        │  1. Extractor  ── LLM ──► {type, owner, due,  │
        │                            summary, conf}     │
        │  2. Store (SQLite: loose_ends table)          │
        │  3. Scheduler (APScheduler) ─► finds overdue /│
        │       stale ─► sends Block Kit nudge          │
        │  4. Actions: Done / Snooze / Reassign / Escalate
        │  5. App Home dashboard (Block Kit sections)   │
        │  6. /looseends ask ─► RTS context ─► answer    │
        └───────┬───────────────────────────┬───────────┘
                │ RTS API                    │ MCP call (Escalate)
                ▼                            ▼
     ┌──────────────────────┐    ┌────────────────────────────┐
     │  Slack RTS search     │    │  Loose Ends MCP Server      │
     │  (context grounding)  │    │  tool: create_ticket()      │
     └──────────────────────┘    │  (mock Jira/Linear → JSON)  │
                                  └────────────────────────────┘
```

## Data model — `loose_ends` table

| column          | type              | notes                                                        |
|-----------------|-------------------|--------------------------------------------------------------|
| `id`            | TEXT PRIMARY KEY  | uuid4                                                        |
| `type`          | TEXT              | `commitment` \| `unanswered_question`                       |
| `owner_user_id` | TEXT              | Slack user id of the person on the hook                     |
| `channel_id`    | TEXT              | source channel                                              |
| `message_ts`    | TEXT              | source message ts (also used for de-dup)                   |
| `thread_ts`     | TEXT (nullable)   | parent thread ts if any                                     |
| `summary`       | TEXT              | short human summary, e.g. "send the Q3 deck"               |
| `due_at`        | INTEGER (nullable)| epoch **ms**; null if unknown / not a commitment           |
| `status`        | TEXT              | `open` \| `done` \| `snoozed` \| `reassigned` \| `escalated`; default `open` |
| `confidence`    | REAL              | 0..1 from the extractor                                     |
| `created_at`    | INTEGER           | epoch ms                                                    |
| `updated_at`    | INTEGER           | epoch ms                                                    |
| `ticket_ref`    | TEXT (nullable)   | set on escalate, e.g. "LE-1042"                            |
| `nudged_at`     | INTEGER (nullable)| epoch ms of last nudge; anti-spam (added in Phase 5)       |

Unique index on `message_ts` to prevent duplicate captures.

## `src/db.py` — exported functions

`create_loose_end(obj)`, `get_by_id(id)`, `list_by_status(status)`, `list_by_owner(user_id)`,
`list_open()`, `update_status(id, status, extra={})`, `set_due(id, due_at)`,
`reassign(id, new_owner_id)`, `set_ticket_ref(id, ref)`, `set_nudged(id, ts)`.

## `src/llm.py` — extractor contract

`extract_loose_end(text, context=None)` returns strict JSON (parsed defensively):

```json
{
  "is_loose_end": true,
  "type": "commitment | unanswered_question | null",
  "summary": "short string | null",
  "due_hint": "raw phrase like 'friday', 'tonight', 'by EOD' | null",
  "confidence": 0.0
}
```

Conservative: only flag genuine first-person commitments ("I'll…", "on it, will do X by Y")
or clear open questions. Reject smalltalk / jokes / vague statements. False positives are
worse than misses. Low temperature.

## Slack configuration (in the app manifest)

**Bot scopes:** `app_mentions:read`, `channels:history`, `groups:history`, `chat:write`,
`commands`, `im:write`, `im:history`, `users:read`, `reactions:write`.

**Event subscriptions (bot events):** `app_mention`, `message.channels`, `message.groups`,
`app_home_opened`.

**Other:** Socket Mode enabled, Interactivity enabled, App Home **Home tab enabled**,
App Home **Messages tab enabled** (REQUIRED — the bot DMs nudges; without it
`chat.postMessage` to a DM fails with `messages_tab_disabled`), `/looseends` slash command.

**App-Level Token** scope (manual): `connections:write`.

**RTS (Phase 8, optional):** user token (`xoxp-…`) with `search:read.public`
(+ optionally `search:read.im`, `search:read.mpim`, `search:read.private`).

## Environment variables (`.env`)

- `SLACK_BOT_TOKEN` (`xoxb-…`)
- `SLACK_APP_TOKEN` (`xapp-…`, Socket Mode)
- `SLACK_SIGNING_SECRET`
- `DGRID_API_KEY` (DGrid AI gateway key)
- `DGRID_BASE_URL` (default `https://api.dgrid.ai/v1`)
- `DGRID_MODEL` (default `anthropic/claude-sonnet-4.6`; cheaper swap: `deepseek/deepseek-v3.2`)
- `SLACK_USER_TOKEN` (`xoxp-…`, optional — RTS)
- `CONFIDENCE_THRESHOLD` (default `0.6`)
- `STALE_HOURS` (default `4`)

**LLM access:** DGrid is OpenAI-compatible. Use the `openai` SDK with
`base_url=DGRID_BASE_URL`, `api_key=DGRID_API_KEY`. Model IDs are provider-prefixed
(e.g. `anthropic/claude-sonnet-4.6`, `deepseek/deepseek-v3.2`, `x-ai/grok-4.20-non-reasoning`).
