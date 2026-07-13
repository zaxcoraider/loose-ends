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

    removed = wipe()
    print(f"wiped {removed} existing loose end(s)")
    if "--wipe" in sys.argv:
        print("clean slate. (no seed data — capture everything live)")
        return

    channel = pick_channel(client)
    if not channel:
        print("! no channel found — invite the bot to a channel, or pass --channel C…")
        return

    me = None
    try:
        me = client.auth_test().get("user_id")
    except Exception:  # noqa: BLE001
        pass

    history = recent_messages(client, channel)
    now = _now()

    for summary, le_type, due_offset, keyword in SEEDS:
        # Bind to a real message if one matches, so the permalink resolves on camera.
        match = next(
            (m for m in history if keyword in (m.get("text") or "").lower()), None
        )
        message_ts = match["ts"] if match else f"{(now - DAY) / 1000:.6f}"
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
