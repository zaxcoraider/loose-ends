"""Reset Loose Ends to a clean, known state for the demo.

    .venv/Scripts/python.exe -u scripts/seed_demo.py            # wipe + seed
    .venv/Scripts/python.exe -u scripts/seed_demo.py --wipe     # wipe only
    .venv/Scripts/python.exe -u scripts/seed_demo.py --channel C0123ABC

Why: a demo must be reproducible take after take. Left alone, the DB accumulates
old items that nudge you mid-recording and make the dashboard look random.

What it seeds (for the App Home dashboard to look alive from frame one):
  1. an OVERDUE commitment      -> genuinely overdue, so it nudges on the next tick
                                   (or immediately via `/looseends check`)
  2. an UPCOMING commitment     -> shows the "Upcoming" group
  3. a stale UNANSWERED question-> shows the "Questions" group

Where possible each seeded item is bound to a REAL message in the channel (matched by
keyword against recent history) so "Jump to original message" permalinks work on camera.
If no match is found it falls back to a synthetic ts — the card still renders, just
without the source link.

The two "noise" messages that must NOT be flagged are typed live during the demo
(see DEMO_SCRIPT.md) — that's the point, they have to run through the real extractor.
"""
import os
import sys
import time

sys.path.insert(0, ".")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from slack_sdk import WebClient  # noqa: E402

from src import config, db  # noqa: E402

HOUR = 3600_000
DAY = 24 * HOUR


def _now() -> int:
    return int(time.time() * 1000)


# summary, type, due_at offset from now (None = no due date), keyword to match a real message
SEEDS = [
    ("send the Q3 deck", "commitment", -3 * HOUR, "q3"),
    ("share the roadmap doc", "commitment", +6 * HOUR, "roadmap"),
    ("who's handling the prod deploy tonight?", "unanswered_question", None, "prod deploy"),
]


def pick_channel(client) -> str | None:
    """--channel arg, else $DEMO_CHANNEL, else the first public channel the bot is in.

    The auto-detect path needs the `channels:read` scope, which this app doesn't have
    (it only has channels:history). Rather than force a reinstall for a dev script,
    set DEMO_CHANNEL in .env or pass --channel.
    """
    if "--channel" in sys.argv:
        return sys.argv[sys.argv.index("--channel") + 1]
    if os.environ.get("DEMO_CHANNEL"):
        return os.environ["DEMO_CHANNEL"]
    try:
        r = client.conversations_list(types="public_channel", limit=200)
        for c in r.get("channels", []):
            if c.get("is_member"):
                return c["id"]
    except Exception as e:  # noqa: BLE001
        print(f"  ! couldn't list channels ({e})")
    return None


def recent_messages(client, channel: str) -> list[dict]:
    try:
        r = client.conversations_history(channel=channel, limit=200)
        return [m for m in r.get("messages", []) if m.get("user") and not m.get("bot_id")]
    except Exception as e:  # noqa: BLE001
        print(f"  ! couldn't read history ({e}) — seeding with synthetic timestamps")
        return []


def wipe() -> int:
    with db._lock:
        cur = db._conn.execute("DELETE FROM loose_ends")
        db._conn.commit()
        return cur.rowcount


def main() -> None:
    client = WebClient(token=config.SLACK_BOT_TOKEN)

    # Resolve everything we need BEFORE destroying anything. Wiping first and *then*
    # discovering we have no channel leaves an empty DB and no demo — which is exactly
    # what happened once, minutes before a take.
    wipe_only = "--wipe" in sys.argv
    channel = None if wipe_only else pick_channel(client)
    if not wipe_only and not channel:
        print("! no channel found — nothing wiped. Pass --channel C… or set DEMO_CHANNEL in .env")
        return

    me = None
    try:
        me = client.auth_test().get("user_id")
    except Exception:  # noqa: BLE001
        pass

    # Read history BEFORE the wipe as well: a bad channel id must leave the DB untouched,
    # not empty it and then bail. Everything that can fail, fails while the data is safe.
    history = [] if wipe_only else recent_messages(client, channel)
    if not wipe_only and not history and "--force" not in sys.argv:
        print(
            f"! read no messages from {channel} — is that channel id right, and is the bot in it?\n"
            "  Nothing was wiped, nothing seeded — your existing items are untouched.\n"
            "  Re-run with --force if you really want synthetic timestamps (dead permalinks)."
        )
        return

    removed = wipe()
    print(f"wiped {removed} existing loose end(s)")
    if wipe_only:
        print("clean slate. (no seed data — capture everything live)")
        return

    now = _now()

    for i, (summary, le_type, due_offset, keyword) in enumerate(SEEDS):
        # Bind to a real message if one matches, so the permalink resolves on camera.
        match = next(
            (m for m in history if keyword in (m.get("text") or "").lower()), None
        )
        # `i` keeps synthetic timestamps distinct: message_ts carries a unique index, so
        # without it every fallback seed collides on the same second and dedup silently
        # drops all but the first — you'd get 1 card on camera instead of 3.
        message_ts = match["ts"] if match else f"{(now - DAY) / 1000 + i:.6f}"
        owner = (match.get("user") if match else None) or me
        if not owner:
            print("! couldn't determine an owner (auth_test failed) — skipping")
            return

        row = db.create_loose_end(
            {
                "type": le_type,
                "owner_user_id": owner,
                "channel_id": channel,
                "message_ts": message_ts,
                "summary": summary,
                "due_at": now + due_offset if due_offset is not None else None,
                "confidence": 0.9,
            }
        )
        if row is None:
            print(f"  · {summary!r} already tracked (dedup) — skipped")
            continue

        # Questions go stale on `created_at`, not on the age of the message. A row created
        # right now is zero hours old, so it can never trip STALE_HOURS and no question card
        # would ever fire — the Escalate step of the demo would have nothing to click.
        # Backdate it so the staleness is REAL, not staged: the scheduler applies its normal
        # rule to a question that genuinely has been sitting unanswered.
        if le_type == "unanswered_question":
            stale_at = now - int((config.STALE_HOURS + 2) * HOUR)
            with db._lock:
                db._conn.execute(
                    "UPDATE loose_ends SET created_at = ? WHERE id = ?", (stale_at, row["id"])
                )
                db._conn.commit()

        when = (
            "no due date"
            if due_offset is None
            else ("OVERDUE" if due_offset < 0 else f"due in {due_offset // HOUR}h")
        )
        src = "real message ✔" if match else "synthetic ts (no permalink)"
        print(f"  + [{le_type}] {summary} — {when} — {src}")

    print(f"\nseeded into channel {channel}. Open the App Home tab to see the dashboard.")
    print("Force the nudge on camera with:  /looseends check")


if __name__ == "__main__":
    main()
