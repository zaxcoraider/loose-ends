"""Quick inspector: print every loose end in the real DB.

Run either way:
    .venv/Scripts/python.exe -m scripts.list_ends
    .venv/Scripts/python.exe -u scripts/list_ends.py
"""
import sys
from datetime import datetime

sys.path.insert(0, ".")  # so running this by path (not -m) still finds `src`

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from src import db  # noqa: E402


def fmt(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%a %m-%d %H:%M") if ms else "-"


def main():
    with db._lock:  # read everything, any status
        rows = [dict(r) for r in db._conn.execute(
            "SELECT * FROM loose_ends ORDER BY created_at DESC"
        ).fetchall()]
    print(f"{len(rows)} loose end(s)\n" + "-" * 90)
    for r in rows:
        print(
            f"[{r['status']:<10}] {r['type']:<20} owner={r['owner_user_id']} "
            f"due={fmt(r['due_at'])} conf={r['confidence']:.2f}\n"
            f"    {r['summary']}   (ch={r['channel_id']} ts={r['message_ts']})"
        )


if __name__ == "__main__":
    main()
