"""Block Kit card rendering for Loose Ends nudges.

One state-aware renderer, `render_card(loose_end, permalink)`, used by both the
scheduler (DM nudges) and the App Home dashboard. The card always reflects the
loose end's current status — active items show action buttons, resolved items
show a confirmation context line. No dead buttons.
"""
import time
from datetime import datetime

from . import config

ACTIVE_STATUSES = {"open", "snoozed", "reassigned"}


def ticket_note(ref: str | None) -> str:
    """How an escalated item announces its ticket.

    Only ever renders a link when a real tracker is configured (TICKET_BASE_URL).
    In the default demo the connector stores tickets locally, so we show the ref as
    plain text — a dead link that 404s is worse than no link at all.
    """
    if not ref:
        return "📌 Escalated to a ticket"
    if config.TICKET_BASE_URL:
        return f"📌 Escalated → <{config.TICKET_BASE_URL}/{ref}|*{ref}*>"
    return f"📌 Escalated → `{ref}` · created via the MCP connector"


def _now_ms() -> int:
    return int(time.time() * 1000)


def slack_date(epoch_ms: int, fmt: str = "{date_short_pretty} at {time}") -> str:
    """Slack's native date token — renders in each VIEWER's timezone, not the server's.

    A nudge that says "due at 6pm" is wrong for half the team. Slack will localise this
    for whoever is reading the card; the pipe-suffix is the fallback if it can't.
    """
    secs = int(epoch_ms / 1000)
    fallback = datetime.fromtimestamp(epoch_ms / 1000).strftime("%a %b %d, %I:%M %p")
    return f"<!date^{secs}^{fmt}|{fallback}>"


def urgency_dot(loose_end: dict) -> str:
    """One glyph carrying the whole status, scannable before any text is read."""
    if loose_end["type"] == "unanswered_question":
        return "💬"
    due = loose_end.get("due_at")
    if not due:
        return "⚪"
    delta_min = (due - _now_ms()) / 60000
    if delta_min < 0:
        return "🔴"
    if delta_min < 120:
        return "🟡"
    return "🟢"


def source_context(loose_end: dict) -> str:
    """Where this came from. `<#C…>` renders the channel name with no channels:read scope."""
    bits = []
    if loose_end.get("channel_id"):
        bits.append(f"in <#{loose_end['channel_id']}>")
    ts = loose_end.get("message_ts")
    if ts:
        try:
            verb = "asked" if loose_end["type"] == "unanswered_question" else "promised"
            bits.append(f"{verb} {slack_date(int(float(ts) * 1000), '{date_short_pretty}')}")
        except (TypeError, ValueError):
            pass
    return " · ".join(bits)


def relative_due(due_at: int | None) -> str:
    """Human phrase for a due timestamp relative to now."""
    if not due_at:
        return "no due date"
    now = _now_ms()
    delta_min = (due_at - now) / 60000
    when = datetime.fromtimestamp(due_at / 1000).strftime("%a %b %d, %I:%M %p")
    if delta_min < 0:
        overdue = -delta_min
        if overdue < 60:
            return f"overdue by {int(overdue)}m"
        if overdue < 60 * 24:
            return f"overdue by {int(overdue // 60)}h"
        return f"overdue since {when}"
    if delta_min < 60:
        return f"due in {int(delta_min)}m"
    if delta_min < 60 * 24:
        return f"due in {int(delta_min // 60)}h"
    return f"due {when}"


def _title(loose_end: dict) -> str:
    if loose_end["type"] == "commitment":
        return "⏰ Still on the hook"
    return "❓ Unanswered question"


def action_row(le_id: str, block_id: str) -> dict:
    """The four actions. One definition, shared by the DM card and the dashboard, so the
    two surfaces can never drift apart."""
    return {
        "type": "actions",
        "block_id": block_id,
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Done"},
                "style": "primary",
                "action_id": "le_done",
                "value": le_id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "😴 Snooze"},
                "action_id": "le_snooze",
                "value": le_id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "↪ Reassign"},
                "action_id": "le_reassign",
                "value": le_id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "📌 Escalate"},
                "style": "danger",
                "action_id": "le_escalate",
                "value": le_id,
                # Escalate is the one irreversible action: it files a real ticket through
                # the MCP connector. Confirm it. Accidentally ticketing your teammate's
                # half-promise is exactly how an accountability bot gets uninstalled.
                "confirm": {
                    "title": {"type": "plain_text", "text": "Create a ticket?"},
                    "text": {
                        "type": "mrkdwn",
                        "text": "This files a tracked ticket through the MCP connector "
                                "and closes this loose end.",
                    },
                    "confirm": {"type": "plain_text", "text": "Escalate"},
                    "deny": {"type": "plain_text", "text": "Cancel"},
                    "style": "danger",
                },
            },
        ],
    }


def render_card(loose_end: dict, permalink: str | None = None) -> list[dict]:
    """Return Block Kit blocks for a loose end in its current state."""
    le_id = loose_end["id"]
    status = loose_end["status"]
    summary = loose_end["summary"]

    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": _title(loose_end)}}
    ]

    # main line — the urgency dot reads before the words do
    main = f"{urgency_dot(loose_end)}  *{summary}*"
    if loose_end["type"] == "commitment":
        main += f"\n_{relative_due(loose_end.get('due_at'))}_"
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": main}})

    # provenance: which channel, when it was said, and a way back to it
    trail = source_context(loose_end)
    if permalink:
        trail = f"{trail} · <{permalink}|↗ jump to message>" if trail else \
                f"<{permalink}|↗ jump to message>"
    if trail:
        blocks.append(
            {"type": "context", "elements": [{"type": "mrkdwn", "text": trail}]}
        )

    if status in ACTIVE_STATUSES:
        blocks.append(action_row(le_id, f"le_actions_{le_id}"))
        if status == "snoozed":
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"😴 Snoozed · {relative_due(loose_end.get('due_at'))}"}
                    ],
                }
            )
        elif status == "reassigned":
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": "↪ Reassigned to you"}],
                }
            )
    else:  # resolved
        if status == "done":
            note = "✅ Marked done"
        elif status == "escalated":
            note = ticket_note(loose_end.get("ticket_ref"))
        else:
            note = "✅ Closed"
        blocks.append(
            {"type": "context", "elements": [{"type": "mrkdwn", "text": note}]}
        )

    return blocks


def fallback_text(loose_end: dict) -> str:
    """Plain-text fallback for notifications / accessibility."""
    return f"{_title(loose_end)}: {loose_end['summary']}"
