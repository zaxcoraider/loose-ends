"""App Home dashboard + slash-command summary rendering.

`publish_home(client, user_id)` renders the viewer's loose ends grouped into
Overdue / Upcoming / Unanswered questions / Recently done, each item carrying the
same action buttons as the DM nudge. Republished after every action to stay in sync.
"""
import logging
import time

from . import db, nudge

log = logging.getLogger("looseends.home")

DONE_STATUSES = {"done", "escalated"}
RECENT_DONE_LIMIT = 5


def _now_ms() -> int:
    return int(time.time() * 1000)


def _divider() -> dict:
    return {"type": "divider"}


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _group_header(text: str) -> dict:
    return {"type": "header", "text": {"type": "plain_text", "text": text}}


def _item_blocks(loose_end: dict, with_buttons: bool = True) -> list[dict]:
    """Compact per-item rendering for the dashboard (summary + due + buttons)."""
    le_id = loose_end["id"]
    line = f"*{loose_end['summary']}*"
    if loose_end["type"] == "commitment":
        line += f"\n_{nudge.relative_due(loose_end.get('due_at'))}_"
    blocks: list[dict] = [{"type": "section", "text": {"type": "mrkdwn", "text": line}}]
    if with_buttons and loose_end["status"] in nudge.ACTIVE_STATUSES:
        blocks.append(
            {
                "type": "actions",
                "block_id": f"home_actions_{le_id}",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "✅ Done"},
                     "style": "primary", "action_id": "le_done", "value": le_id},
                    {"type": "button", "text": {"type": "plain_text", "text": "😴 Snooze"},
                     "action_id": "le_snooze", "value": le_id},
                    {"type": "button", "text": {"type": "plain_text", "text": "↪ Reassign"},
                     "action_id": "le_reassign", "value": le_id},
                    {"type": "button", "text": {"type": "plain_text", "text": "📌 Escalate"},
                     "style": "danger", "action_id": "le_escalate", "value": le_id},
                ],
            }
        )
    elif loose_end["status"] in DONE_STATUSES:
        if loose_end["status"] == "done":
            note = "✅ done"
        else:
            ref = loose_end.get("ticket_ref")
            note = (f"📌 escalated → <https://tickets.looseends.dev/{ref}|{ref}>"
                    if ref else "📌 escalated")
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": note}]})
    return blocks


def _bucket(user_id: str) -> dict:
    """Partition the user's loose ends into dashboard groups."""
    now = _now_ms()
    rows = db.list_by_owner(user_id)
    overdue, upcoming, questions, done = [], [], [], []
    for r in rows:
        if r["status"] in DONE_STATUSES:
            done.append(r)
        elif r["type"] == "unanswered_question":
            questions.append(r)
        elif r["type"] == "commitment":
            if r.get("due_at") and r["due_at"] <= now:
                overdue.append(r)
            else:
                upcoming.append(r)
    done = done[:RECENT_DONE_LIMIT]
    return {"overdue": overdue, "upcoming": upcoming, "questions": questions, "done": done}


def build_home_view(user_id: str) -> dict:
    groups = _bucket(user_id)
    open_count = len(groups["overdue"]) + len(groups["upcoming"]) + len(groups["questions"])
    overdue_count = len(groups["overdue"])

    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f"🪢 *Your loose ends*\nYou have *{open_count}* open · "
                 f"*{overdue_count}* overdue"}},
        _divider(),
    ]

    def add_group(title: str, items: list[dict], empty: str):
        blocks.append(_group_header(title))
        if not items:
            blocks.append({"type": "context",
                           "elements": [{"type": "mrkdwn", "text": empty}]})
            return
        for it in items:
            blocks.extend(_item_blocks(it))

    add_group(f"⏰ Overdue ({len(groups['overdue'])})", groups["overdue"],
              "_Nothing overdue. Nice._")
    add_group(f"🕒 Upcoming ({len(groups['upcoming'])})", groups["upcoming"],
              "_No upcoming commitments._")
    add_group(f"❓ Unanswered questions ({len(groups['questions'])})", groups["questions"],
              "_No open questions._")
    if groups["done"]:
        add_group("✅ Recently done", groups["done"], "")

    blocks.append(_divider())
    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": "Loose Ends · your accountability agent"}]})

    return {"type": "home", "blocks": blocks}


def publish_home(client, user_id: str) -> None:
    try:
        client.views_publish(user_id=user_id, view=build_home_view(user_id))
    except Exception as e:  # noqa: BLE001
        log.warning("home publish failed for %s: %s", user_id, e)


def build_summary_blocks(user_id: str) -> list[dict]:
    """Read-only grouped summary for the /looseends ephemeral response."""
    groups = _bucket(user_id)
    open_count = len(groups["overdue"]) + len(groups["upcoming"]) + len(groups["questions"])
    blocks: list[dict] = [
        _section(f"🪢 *You have {open_count} open loose end(s) · "
                 f"{len(groups['overdue'])} overdue*")
    ]

    def add(title: str, items: list[dict]):
        if not items:
            return
        lines = []
        for it in items:
            suffix = (f" — _{nudge.relative_due(it.get('due_at'))}_"
                      if it["type"] == "commitment" else "")
            lines.append(f"• {it['summary']}{suffix}")
        blocks.append(_section(f"*{title}*\n" + "\n".join(lines)))

    add("⏰ Overdue", groups["overdue"])
    add("🕒 Upcoming", groups["upcoming"])
    add("❓ Unanswered questions", groups["questions"])
    if open_count == 0:
        blocks.append(_section("_You're all caught up. 🎉_"))
    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": "Open the Loose Ends *Home* tab for buttons."}]})
    return blocks
