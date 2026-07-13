"""Smoke test: RTS + `/looseends ask`, without touching Slack's UI.

    .venv/Scripts/python.exe -u scripts/rts_smoke.py
    .venv/Scripts/python.exe -u scripts/rts_smoke.py U123ABC "what did I promise?"

Verifies, in order: user token present? → assistant.search.info → assistant.search.context
→ the full grounded answer the slash command would render. Works (DB-only) with no token.
Defaults to whichever user the bot token belongs to.
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

client = WebClient(token=config.SLACK_BOT_TOKEN)


def _default_user() -> str:
    """Whoever installed the app — never hardcode a person's id into the repo."""
    try:
        return client.auth_test()["user_id"]
    except Exception as e:  # noqa: BLE001
        sys.exit(f"couldn't resolve a user from SLACK_BOT_TOKEN ({e}); pass one: "
                 f"rts_smoke.py U123ABC \"your question\"")


user_id = sys.argv[1] if len(sys.argv) > 1 else _default_user()
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
for b in ask.build_ask_blocks(client, user_id, question):
    if b["type"] == "section":
        print(b["text"]["text"])
    elif b["type"] == "context":
        print(b["elements"][0]["text"])
