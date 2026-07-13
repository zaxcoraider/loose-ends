"""Loose Ends — the nudge scheduler.

APScheduler runs `run_checks` every CHECK_INTERVAL_MINUTES. Each tick:
  • overdue commitments → DM the owner a nudge card
  • stale questions with no non-author replies → DM the asker
Anti-spam: after nudging, `nudged_at` is stamped; we won't re-nudge until the
RENUDGE_HOURS cooldown passes.
"""
import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler

from . import config, db, nudge

log = logging.getLogger("looseends.scheduler")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_permalink(client, loose_end: dict) -> str | None:
    try:
        r = client.chat_getPermalink(
            channel=loose_end["channel_id"], message_ts=loose_end["message_ts"]
        )
        return r.get("permalink")
    except Exception as e:  # noqa: BLE001
        log.warning("permalink failed for %s: %s", loose_end["id"], e)
        return None


def send_nudge(client, loose_end: dict) -> bool:
    """DM the owner the nudge card. Returns True if sent."""
    owner = loose_end["owner_user_id"]
    try:
        dm = client.conversations_open(users=owner)
        dm_channel = dm["channel"]["id"]
        permalink = _safe_permalink(client, loose_end)
        client.chat_postMessage(
            channel=dm_channel,
            text=nudge.fallback_text(loose_end),
            blocks=nudge.render_card(loose_end, permalink),
        )
        db.set_nudged(loose_end["id"], _now_ms())
        log.info("nudged %s about %s", owner, loose_end["summary"])
        return True
    except Exception as e:  # noqa: BLE001 — one bad nudge must not kill the tick
        log.warning("nudge failed for %s: %s", loose_end["id"], e)
        return False


def _question_has_reply(client, loose_end: dict) -> bool:
    """True if the question's thread has a reply from someone other than the asker."""
    thread_root = loose_end.get("thread_ts") or loose_end["message_ts"]
    try:
        r = client.conversations_replies(
            channel=loose_end["channel_id"], ts=thread_root, limit=20
        )
        for m in r.get("messages", []):
            if m.get("ts") == thread_root:
                continue  # the question itself
            if m.get("user") and m["user"] != loose_end["owner_user_id"]:
                return True
    except Exception as e:  # noqa: BLE001 — if we can't check, assume unanswered
        log.warning("replies check failed for %s: %s", loose_end["id"], e)
    return False


def run_checks(client) -> dict:
    """One scheduler pass. Returns a small summary dict."""
    now = _now_ms()
    cooldown_cutoff = now - int(config.RENUDGE_HOURS * 3600_000)
    stale_before = now - int(config.STALE_HOURS * 3600_000)

    sent_commitments = 0
    for le in db.list_due_commitments(now, cooldown_cutoff):
        if send_nudge(client, le):
            sent_commitments += 1

    sent_questions = 0
    for le in db.list_stale_questions(stale_before, cooldown_cutoff):
        if _question_has_reply(client, le):
            continue  # someone answered — leave it alone
        if send_nudge(client, le):
            sent_questions += 1

    summary = {"commitments": sent_commitments, "questions": sent_questions}
    if sent_commitments or sent_questions:
        log.info("tick sent nudges: %s", summary)
    return summary


def start(app) -> BackgroundScheduler:
    """Start the recurring scheduler. Uses the Bolt app's web client."""
    client = app.client
    sched = BackgroundScheduler(daemon=True)
    # An interval trigger already waits one full interval before its first run, so there
    # is nothing to suppress at boot. Passing next_run_time=None here does NOT do that —
    # it adds the job in a paused state, and the nudges never fire on their own at all.
    sched.add_job(
        lambda: run_checks(client),
        "interval",
        minutes=config.CHECK_INTERVAL_MINUTES,
        id="looseends_checks",
    )
    sched.start()
    log.info("scheduler started (every %s min)", config.CHECK_INTERVAL_MINUTES)
    return sched
