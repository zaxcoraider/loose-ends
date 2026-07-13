"""Smoke test: run example messages through the extractor + due-date parser.

Run:  .venv/Scripts/python.exe -m scripts.extract_smoke
Eyeball the table: real commitments/questions should flag, noise should NOT.
Makes real DGrid API calls (needs DGRID_API_KEY in .env).
"""
import os
import sys
import time
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, ".")  # so running this by path (not -m) still finds `src`

from src import llm  # noqa: E402
from src import duedate  # noqa: E402

NOW_MS = int(time.time() * 1000)

# (message, expected_is_loose_end)  — expectation is just for our own eyeballing
EXAMPLES = [
    ("I'll send the Q3 deck by Friday.", True),
    ("on it — will push the hotfix tonight", True),
    ("Can someone review PR #42 today? blocking the release", True),
    ("who owns the staging deploy?", True),
    ("I'll take the onboarding doc, should have it done by EOD", True),
    ("lol that meeting was wild", False),
    ("the build is green ✅", False),
    ("gm everyone ☕", False),
    ("I sent the report yesterday", False),  # past tense — NOT open
    ("thanks, appreciate it!", False),
    ("I'll circle back next week with the pricing", True),
    ("should we use postgres or sqlite here?", True),  # question, arguable
]


def main():
    print(f"{'FLAG':<5} {'CONF':<5} {'TYPE':<20} {'DUE':<20} MESSAGE")
    print("-" * 100)
    correct = 0
    for text, expected in EXAMPLES:
        r = llm.extract_loose_end(text)
        is_le = r["is_loose_end"]
        due_ms = duedate.parse_due(r.get("due_hint"), NOW_MS) if is_le else None
        due_str = (
            datetime.fromtimestamp(due_ms / 1000).strftime("%a %m-%d %H:%M")
            if due_ms
            else "-"
        )
        flag = "✅" if is_le else "·"
        match = "  " if is_le == expected else " ⚠️"
        if is_le == expected:
            correct += 1
        print(
            f"{flag:<5} {r['confidence']:<5.2f} {str(r['type'] or '-'):<20} "
            f"{due_str:<20} {text}{match}"
        )
    print("-" * 100)
    print(f"matched expectation: {correct}/{len(EXAMPLES)}  "
          f"(⚠️ = disagreed with my guess — eyeball those, my guesses aren't gospel)")


if __name__ == "__main__":
    main()
