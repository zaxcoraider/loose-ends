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
    """Compact per-item rendering for the dashboard (summary + due + provenance + buttons)."""
    le_id = loose_end["id"]
    line = f"{nudge.urgency_dot(loose_end)}  *{loose_end['summary']}*"
    if loose_end["type"] == "commitment":
        line += f"\n_{nudge.relative_due(loose_end.get('due_at'))}_"
    blocks: list[dict] = [{"type": "section", "text": {"type": "mrkdwn", "text": line}}]

    trail = nudge.source_context(loose_end)
    if trail:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": trail}]})

    if with_buttons and loose_end["status"] in nudge.ACTIVE_STATUSES:
        blocks.append(nudge.action_row(le_id, f"home_actions_{le_id}"))
    elif loose_end["status"] in DONE_STATUSES:
        note = ("✅ Done" if loose_end["status"] == "done"
                else nudge.ticket_note(loose_end.get("ticket_ref")))
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
    # Most-overdue first, soonest-due first: the top of the list is always the thing
    # that most deserves the next minute of your attention.
    overdue.sort(key=lambda r: r.get("due_at") or 0)
    upcoming.sort(key=lambda r: r.get("due_at") or 0)
    done.sort(key=lambda r: r.get("updated_at") or 0, reverse=True)
    done = done[:RECENT_DONE_LIMIT]
    return {"overdue": overdue, "upcoming": upcoming, "questions": questions, "done": done}


def _first_run_blocks() -> list[dict]:
    """What a brand-new user sees. Never show four empty buckets and nothing else."""
    return [
        _section("🪢 *Your loose ends*"),
        _divider(),
        _section(
            "*Nothing tracked yet.*\n\n"
            "Invite me to a channel and I'll start watching for the things that get "
            "dropped:\n"
            "• *Commitments* — “I'll send the deck Friday”\n"
            "• *Unanswered questions* — “who owns the staging deploy?”\n\n"
            "When one goes overdue or goes stale, I'll DM you privately — never a "
            "public call-out — with buttons to mark it done, snooze it, hand it off, "
            "or turn it into a ticket."
        ),
        {"type": "context", "elements": [{"type": "mrkdwn", "text":
            "I stay quiet otherwise. Chit-chat, jokes, and status updates are ignored."}]},
    ]


def _hero(open_count: int, overdue_count: int) -> list[dict]:
    """The top of the dashboard: state in one sentence, then the controls.

    The headline is written to be *read*, not parsed — "1 needs you now" beats
    "1 overdue" because it says what to do about it.
    """
    if overdue_count:
        headline = f"*{overdue_count} needs you now* · {open_count} open in total"
        mood = "🔴"
    elif open_count:
        headline = f"*Nothing overdue* · {open_count} open, all still on track"
        mood = "🟢"
    else:
        headline = "*You're all caught up.* Nothing is hanging."
        mood = "✨"

    return [
        {"type": "header", "text": {"type": "plain_text", "text": "🪢 Loose Ends"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"{mood}  {headline}"}},
        {
            "type": "actions",
            "block_id": "home_controls",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔔 Check now"},
                    "action_id": "home_check",
                    "value": "check",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔄 Refresh"},
                    "action_id": "home_refresh",
                    "value": "refresh",
                },
            ],
        },
        _divider(),
    ]


def build_home_view(user_id: str) -> dict:
    groups = _bucket(user_id)
    open_count = len(groups["overdue"]) + len(groups["upcoming"]) + len(groups["questions"])
    overdue_count = len(groups["overdue"])

    if open_count == 0 and not groups["done"]:
        return {"type": "home", "blocks": _first_run_blocks()}

    blocks: list[dict] = _hero(open_count, overdue_count)

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
