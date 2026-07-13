"""Phase 8 smoke test: RTS + /looseends ask, without touching Slack's UI.

    .venv/Scripts/python.exe -u scripts/rts_smoke.py U0BGTGBPQUU "what did I commit to this week?"

Verifies, in order: user token present? → assistant.search.info → assistant.search.context
→ the full grounded answer the slash command would render. Works (DB-only) with no token.
"""
import json
import sys

sys.path.insert(0, ".")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from slack_sdk import WebClient  # noqa: E402

from src import ask, config, rts  # noqa: E402

user_id = sys.argv[1] if len(sys.argv) > 1 else "U0BGTGBPQUU"
question = sys.argv[2] if len(sys.argv) > 2 else "what did I commit to this week?"

print(f"RTS enabled (user token present): {rts.is_enabled()}")

if rts.is_enabled():
    print("\n-- assistant.search.info --")
    print(json.dumps(rts.info(), indent=2)[:800])

    print("\n-- assistant.search.context --")
    found = rts.search(question, limit=5)
    print(f"ok={found.ok} error={found.error} reason={found.reason} hits={len(found.hits)}")
    for h in found.hits:
        print(f"  #{h.get('channel_name')} @{h.get('author_name')}: "
              f"{(h.get('content') or '')[:80]}")
else:
    print("(no usable SLACK_USER_TOKEN — answer will be DB-only, the supported fallback)")

print(f"\n-- /looseends ask {question} --")
client = WebClient(token=config.SLACK_BOT_TOKEN)
for b in ask.build_ask_blocks(client, user_id, question):
    if b["type"] == "section":
        print(b["text"]["text"])
    elif b["type"] == "context":
        print(b["elements"][0]["text"])
