"""Loose Ends — Bolt for Python app (Socket Mode).

Wires everything together: channel messages → LLM extractor → SQLite (with a 👀
reaction on capture), the Done/Snooze/Reassign/Escalate buttons and their modals,
the App Home dashboard, and the /looseends command.
"""
import json
import logging
import sys
import time

try:  # Windows consoles default to cp1252 and choke on emoji in logs
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from . import ask, config, db, duedate, home, llm, mcp_client, nudge, rts, scheduler

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("looseends")

config.require("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_SIGNING_SECRET")

app = App(
    token=config.SLACK_BOT_TOKEN,
    signing_secret=config.SLACK_SIGNING_SECRET,
)


@app.event("app_mention")
def handle_app_mention(event, say):
    """Reply when someone @-mentions the bot."""
    say(
        text="🪢 Loose Ends is online.",
        thread_ts=event.get("thread_ts") or event.get("ts"),
    )


@app.event("app_home_opened")
def handle_home_opened(event, client):
    """Render the viewer's dashboard when they open the App Home tab."""
    home.publish_home(client, event["user"])


def _ts_to_ms(ts: str) -> int:
    """Slack ts like '1710000000.000200' -> epoch ms."""
    return int(float(ts) * 1000)


@app.event("message")
def handle_message(event, client, logger):
    """Live capture: extract loose ends from human channel messages and store them."""
    # Ignore edits, deletes, joins, and anything the bots say.
    if event.get("subtype") or event.get("bot_id"):
        return

    text = (event.get("text") or "").strip()
    user = event.get("user")
    channel = event.get("channel")
    ts = event.get("ts")
    if not text or not user or not channel or not ts:
        return

    # Cheap pre-filter: skip trivially short messages before spending an LLM call.
    if len(text) < 6:
        return

    # Skip if we've already captured this exact message.
    if db.get_by_message_ts(ts):
        return

    result = llm.extract_loose_end(text)
    if not result["is_loose_end"] or result["confidence"] < config.CONFIDENCE_THRESHOLD:
        return

    due_at = None
    if result["type"] == "commitment":
        due_at = duedate.parse_due(result.get("due_hint"), _ts_to_ms(ts))

    row = db.create_loose_end(
        {
            "type": result["type"],
            "owner_user_id": user,
            "channel_id": channel,
            "message_ts": ts,
            "thread_ts": event.get("thread_ts"),
            "summary": result["summary"] or text[:80],
            "due_at": due_at,
            "confidence": result["confidence"],
        }
    )
    if row is None:  # lost a de-dup race
        return

    log.info(
        "captured %s (conf=%.2f, due=%s): %s",
        row["type"], row["confidence"], row["due_at"], row["summary"],
    )

    # Visible signal in the demo that Loose Ends noticed.
    try:
        client.reactions_add(channel=channel, timestamp=ts, name="eyes")
    except Exception as e:  # noqa: BLE001 — a failed reaction must not lose the capture
        logger.warning("reaction failed: %s", e)


# ── action button handlers ───────────────────────────────────────
def _msg_ctx(body: dict) -> dict | None:
    """If the interaction came from a message (a DM nudge), return where to update it."""
    container = body.get("container", {})
    if container.get("type") == "message" and body.get("channel"):
        return {"channel": body["channel"]["id"], "message_ts": container["message_ts"]}
    return None


def _update_message(client, msg_ctx: dict | None, loose_end: dict) -> None:
    if not msg_ctx:
        return
    permalink = scheduler._safe_permalink(client, loose_end)
    try:
        client.chat_update(
            channel=msg_ctx["channel"],
            ts=msg_ctx["message_ts"],
            text=nudge.fallback_text(loose_end),
            blocks=nudge.render_card(loose_end, permalink),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("card update failed: %s", e)


@app.action("le_done")
def on_done(ack, body, client):
    ack()
    le_id = body["actions"][0]["value"]
    le = db.update_status(le_id, "done")
    if le:
        _update_message(client, _msg_ctx(body), le)
        home.publish_home(client, body["user"]["id"])


@app.action("le_escalate")
def on_escalate(ack, body, client, respond):
    ack()
    le_id = body["actions"][0]["value"]
    le = db.get_by_id(le_id)
    if not le:
        return
    permalink = scheduler._safe_permalink(client, le)

    # Call the open-source Loose Ends MCP server to create a real ticket.
    ticket = mcp_client.create_ticket(
        title=le["summary"],
        description=f"Escalated from a Slack {le['type'].replace('_', ' ')} via Loose Ends.",
        assignee=le["owner_user_id"],
        source_permalink=permalink or "",
    )

    if not ticket:
        # Never fail silently. A button that does nothing when you press it is the
        # worst possible outcome — the user can't tell broken from ignored.
        msg = ("⚠️ Couldn't reach the ticket service, so nothing was created and "
               f"*{le['summary']}* is still open. Try Escalate again in a moment.")
        try:
            respond(response_type="ephemeral", text=msg)
        except Exception:  # noqa: BLE001 — App Home clicks have no response_url
            try:
                dm = client.conversations_open(users=body["user"]["id"])
                client.chat_postMessage(channel=dm["channel"]["id"], text=msg)
            except Exception as e:  # noqa: BLE001
                log.warning("couldn't report escalate failure to %s: %s",
                            body["user"]["id"], e)
        return

    le = db.update_status(le_id, "escalated", {"ticket_ref": ticket["ref"]})
    if le:
        _update_message(client, _msg_ctx(body), le)
        home.publish_home(client, body["user"]["id"])
    log.info("escalated %s -> %s", le_id, ticket["ref"])


# ── App Home controls ────────────────────────────────────────────
@app.action("home_refresh")
def on_home_refresh(ack, body, client):
    ack()
    home.publish_home(client, body["user"]["id"])


@app.action("home_check")
def on_home_check(ack, body, client):
    """Run the real overdue/stale sweep from the dashboard. Same code path as the timer —
    it nudges what is genuinely due, and nothing else."""
    ack()
    user_id = body["user"]["id"]
    summary = scheduler.run_checks(client)
    sent = summary["commitments"] + summary["questions"]
    home.publish_home(client, user_id)
    try:
        dm = client.conversations_open(users=user_id)
        client.chat_postMessage(
            channel=dm["channel"]["id"],
            text=(f"✅ Checked — sent {sent} nudge(s)." if sent
                  else "✅ Checked — nothing is overdue or stale right now."),
        )
    except Exception as e:  # noqa: BLE001 — the sweep still ran; only the receipt failed
        log.warning("couldn't confirm check to %s: %s", user_id, e)


# ── snooze (modal) ───────────────────────────────────────────────
def _snooze_modal(private_metadata: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "le_snooze_submit",
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "Snooze loose end"},
        "submit": {"type": "plain_text", "text": "Snooze"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "snooze",
                "label": {"type": "plain_text", "text": "Remind me again in…"},
                "element": {
                    "type": "radio_buttons",
                    "action_id": "choice",
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "Tomorrow"},
                        "value": "tomorrow",
                    },
                    "options": [
                        {"text": {"type": "plain_text", "text": "1 hour"}, "value": "1h"},
                        {"text": {"type": "plain_text", "text": "Tomorrow"}, "value": "tomorrow"},
                        {"text": {"type": "plain_text", "text": "Next week"}, "value": "next_week"},
                    ],
                },
            }
        ],
    }


def _snooze_due(choice: str) -> int | None:
    now = int(time.time() * 1000)
    if choice == "1h":
        return now + 3600_000
    if choice == "tomorrow":
        return duedate.parse_due("tomorrow", now)
    if choice == "next_week":
        return duedate.parse_due("next week", now)
    return None


@app.action("le_snooze")
def on_snooze(ack, body, client):
    ack()
    le_id = body["actions"][0]["value"]
    pm = json.dumps({"le_id": le_id, "msg": _msg_ctx(body)})
    client.views_open(trigger_id=body["trigger_id"], view=_snooze_modal(pm))


@app.view("le_snooze_submit")
def on_snooze_submit(ack, body, view, client):
    ack()
    meta = json.loads(view["private_metadata"])
    choice = view["state"]["values"]["snooze"]["choice"]["selected_option"]["value"]
    le = db.update_status(
        meta["le_id"], "snoozed", {"due_at": _snooze_due(choice), "nudged_at": None}
    )
    if le:
        _update_message(client, meta.get("msg"), le)
        home.publish_home(client, body["user"]["id"])


# ── reassign (modal) ─────────────────────────────────────────────
def _reassign_modal(private_metadata: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "le_reassign_submit",
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "Reassign loose end"},
        "submit": {"type": "plain_text", "text": "Reassign"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "reassign",
                "label": {"type": "plain_text", "text": "Hand off to…"},
                "element": {"type": "users_select", "action_id": "user"},
            }
        ],
    }


@app.action("le_reassign")
def on_reassign(ack, body, client):
    ack()
    le_id = body["actions"][0]["value"]
    pm = json.dumps({"le_id": le_id, "msg": _msg_ctx(body)})
    client.views_open(trigger_id=body["trigger_id"], view=_reassign_modal(pm))


@app.view("le_reassign_submit")
def on_reassign_submit(ack, body, view, client):
    ack()
    meta = json.loads(view["private_metadata"])
    new_owner = view["state"]["values"]["reassign"]["user"]["selected_user"]
    le = db.reassign(meta["le_id"], new_owner)
    if not le:
        return
    _update_message(client, meta.get("msg"), le)
    # notify the new owner with the same card
    scheduler.send_nudge(client, le)
    # refresh both dashboards: the item left mine, arrived on theirs
    home.publish_home(client, body["user"]["id"])
    home.publish_home(client, new_owner)


# ── slash command ────────────────────────────────────────────────
HELP_TEXT = (
    "🪢 *Loose Ends* — I catch the promises and questions that scroll away.\n\n"
    "• `/looseends` — everything you're on the hook for\n"
    "• `/looseends ask <question>` — e.g. _what did I commit to this week?_\n"
    "• `/looseends check` — run the overdue/stale check right now\n\n"
    "_Invite me to a channel and I'll start watching. I only flag genuine "
    "commitments and open questions — never chit-chat._"
)


@app.command("/looseends")
def handle_command(ack, respond, command, client):
    ack()
    text = (command.get("text") or "").strip()
    verb, _, rest = text.partition(" ")
    verb = verb.lower()
    rest = rest.strip()

    if verb == "help":
        respond(response_type="ephemeral", text=HELP_TEXT)
        return

    if verb == "check":
        # Run the scheduler pass on demand. Same code path the timer uses — it nudges
        # what is genuinely overdue or stale, and nothing else.
        summary = scheduler.run_checks(client)
        sent = summary["commitments"] + summary["questions"]
        respond(
            response_type="ephemeral",
            text=(f"✅ Checked. Sent {sent} nudge(s) — take a look at your DMs."
                  if sent else
                  "✅ Checked. Nothing is overdue or stale right now."),
        )
        return

    if verb == "ask":
        question = rest
        if not question:
            respond(
                response_type="ephemeral",
                text="Ask me something, e.g. `/looseends ask what did I commit to this week?`",
            )
            return
        # ask.* guards its own layers (RTS, LLM, DB) — this is the last-resort net so a
        # slash command can never surface a raw stack trace on camera.
        try:
            blocks = ask.build_ask_blocks(client, command["user_id"], question)
        except Exception as e:  # noqa: BLE001
            log.warning("ask failed: %s", e)
            blocks = home.build_summary_blocks(command["user_id"])
        respond(
            response_type="ephemeral",
            blocks=blocks,
            text=f"Answering: {question}",
        )
        return

    # Anything we don't recognise shouldn't silently do something else.
    if verb and verb not in ("help", "check", "ask"):
        respond(
            response_type="ephemeral",
            text=f"I don't know `{verb}`.\n\n{HELP_TEXT}",
        )
        return

    # bare `/looseends` — show the caller's open items
    respond(
        response_type="ephemeral",
        blocks=home.build_summary_blocks(command["user_id"]),
        text="Your open loose ends",
    )


def main():
    log.info("⚡ Loose Ends running")
    if rts.is_enabled():
        log.info("🔎 Real-Time Search: enabled (user token present)")
    else:
        log.info("🔎 Real-Time Search: OFF — /looseends ask will answer from the DB only")
    scheduler.start(app)
    handler = SocketModeHandler(app, config.SLACK_APP_TOKEN)
    handler.start()


if __name__ == "__main__":
    main()
