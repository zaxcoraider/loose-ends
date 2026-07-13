"""Phase 2 smoke test: insert 2 fake loose ends, list them, mark one done, print results.

Run:  .venv/Scripts/python.exe -m scripts.db_smoke
Uses a throwaway DB file so it never pollutes the real one.
"""
import os
import sys

try:  # Windows consoles default to cp1252 and choke on emoji
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

os.environ["LOOSEENDS_DB"] = "smoke_test.sqlite"  # must be set BEFORE importing db

# clean slate BEFORE importing db (import opens + locks the file on Windows)
if os.path.exists("smoke_test.sqlite"):
    os.remove("smoke_test.sqlite")

from src import db  # noqa: E402


def show(label, rows):
    print(f"\n── {label} ({len(rows)}) ──")
    for r in rows:
        print(
            f"  [{r['status']:<10}] {r['type']:<20} owner={r['owner_user_id']} "
            f"due={r['due_at']} :: {r['summary']}"
        )


def main():
    a = db.create_loose_end(
        {
            "type": "commitment",
            "owner_user_id": "U_ALICE",
            "channel_id": "C_DEMO",
            "message_ts": "1710000000.0001",
            "summary": "send the Q3 deck",
            "due_at": 1710086400000,
            "confidence": 0.92,
        }
    )
    b = db.create_loose_end(
        {
            "type": "unanswered_question",
            "owner_user_id": "U_BOB",
            "channel_id": "C_DEMO",
            "message_ts": "1710000000.0002",
            "summary": "who owns the staging deploy?",
            "confidence": 0.78,
        }
    )
    print(f"inserted a={a['id'][:8]}  b={b['id'][:8]}")

    # de-dup check: same message_ts should return None
    dup = db.create_loose_end(
        {
            "type": "commitment",
            "owner_user_id": "U_ALICE",
            "channel_id": "C_DEMO",
            "message_ts": "1710000000.0001",
            "summary": "duplicate — should be rejected",
        }
    )
    print(f"dedup on same message_ts -> {'REJECTED ✅' if dup is None else 'LEAKED ❌'}")

    show("all open", db.list_open())

    db.update_status(a["id"], "done")
    show("after marking a=done — open", db.list_open())
    show("done", db.list_by_status("done"))
    show("by owner U_BOB", db.list_by_owner("U_BOB"))

    # cleanup
    print("\nsmoke test OK ✅")


if __name__ == "__main__":
    main()
