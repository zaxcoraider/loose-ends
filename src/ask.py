"""`/looseends ask <question>` — a grounded answer about your loose ends.

Two sources, in priority order:
  1. SQLite — what Loose Ends has already tracked for you (authoritative, always available).
  2. Slack Real-Time Search — raw workspace messages for detail + citations (optional).

Both are handed to the LLM, which writes a short cited answer. Every layer degrades:
no RTS token → DB-only answer; LLM down → a plain rendered list. The command always
returns something useful.
"""
import logging

from . import db, llm, nudge, rts, scheduler

log = logging.getLogger("looseends.ask")

MAX_TRACKED = 15
MAX_CONTEXT = 8


def _tracked_for(client, user_id: str) -> list[dict]:
    """The user's loose ends, flattened for the prompt (with due phrase + permalink)."""
    rows = db.list_by_owner(user_id)[:MAX_TRACKED]
    out = []
    for r in rows:
        out.append(
            {
                "type": r["type"],
                "summary": r["summary"],
                "status": r["status"],
                "due_phrase": (
                    nudge.relative_due(r.get("due_at"))
                    if r["type"] == "commitment"
                    else "n/a"
                ),
                "permalink": scheduler._safe_permalink(client, r),
            }
        )
    return out


def _fallback_blocks(user_id: str, tracked: list[dict]) -> list[dict]:
    """If the LLM is unavailable, still answer — just as a plain list."""
    from . import home

    blocks = home.build_summary_blocks(user_id)
    blocks.insert(
        0,
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn",
                 "text": "_Couldn't reach the answer engine — here's your tracked list instead._"}
            ],
        },
    )
    return blocks


def build_ask_blocks(client, user_id: str, question: str) -> list[dict]:
    """Answer `question` for `user_id`. Never raises."""
    tracked = _tracked_for(client, user_id)

    # Search the question as asked. Don't splice in "(from <@U…>)" to bias toward the
    # asker: that isn't Slack search-modifier syntax, so RTS reads it as extra semantic
    # text and it measurably shreds recall (5 hits -> 1 in testing). The user token
    # already limits results to channels this user can see, which is the scoping we want.
    found = rts.search(question, limit=MAX_CONTEXT)

    answer = llm.answer_question(question, tracked, found.hits)
    if not answer:
        return _fallback_blocks(user_id, tracked)

    blocks: list[dict] = [
        {"type": "section",
         "text": {"type": "mrkdwn", "text": f"🪢 *{question}*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": answer}},
    ]

    links = " · ".join(
        f"<{h['permalink']}|#{h.get('channel_name') or 'source'}>"
        for h in found.hits[:5]
        if h.get("permalink")
    )
    if links:
        blocks.append(
            {"type": "context",
             "elements": [{"type": "mrkdwn", "text": f"🔎 Sources: {links}"}]}
        )

    blocks.append(
        {"type": "context",
         "elements": [{"type": "mrkdwn", "text": rts.status_note(found)}]}
    )
    return blocks
