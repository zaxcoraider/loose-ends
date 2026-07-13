"""Block Kit card rendering for Loose Ends nudges.

One state-aware renderer, `render_card(loose_end, permalink)`, used by both the
scheduler (DM nudges) and App Home (Phase 6). The card always reflects the
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


def render_card(loose_end: dict, permalink: str | None = None) -> list[dict]:
    """Return Block Kit blocks for a loose end in its current state."""
    le_id = loose_end["id"]
    status = loose_end["status"]
    summary = loose_end["summary"]

    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": _title(loose_end)}}
    ]

    # main line
    main = f"*{summary}*"
    if loose_end["type"] == "commitment":
        main += f"\n_{relative_due(loose_end.get('due_at'))}_"
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": main}})

    # source link
    if permalink:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"<{permalink}|↗ Jump to original message>"}
                ],
            }
        )

    if status in ACTIVE_STATUSES:
        blocks.append(
            {
                "type": "actions",
                "block_id": f"le_actions_{le_id}",
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
                    },
                ],
            }
        )
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
