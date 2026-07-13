# Loose Ends — 3-Minute Demo Run-of-Show

> How to drive the full product end to end, in order, without a stumble.
> Open on the product, not on a face. Record 1080p.

---

## Before you hit record (5 min)

```bash
# 1. Clean, known state — otherwise old items nudge you mid-take
.venv/Scripts/python.exe -u scripts/seed_demo.py

# 2. MCP server (terminal A)
cd mcp-server && ../.venv/Scripts/python.exe -u server.py

# 3. App (terminal B) — ONE instance only
.venv/Scripts/python.exe -u -m src.app
```

Confirm in the app log: `🔎 Real-Time Search: enabled`.

**Screen setup:** Slack open on the seeded channel. Terminal A (MCP server) visible in a
small window or a second screen — you'll cut to it for the Escalate moment. Close every
other notification source.

**Dashboard should already show:** 1 overdue commitment ("send the Q3 deck"), 1 upcoming
("share the roadmap doc"), 1 unanswered question ("who's handling the prod deploy tonight?").

---

## 0:00–0:15 — Hook. No intro.

Screen is already in Slack. Type into the channel:

> **I'll send the Q3 deck by end of day.**

Loose Ends reacts 👀.

**Say:** *"Loose Ends just caught a promise — nobody asked it to."*

Then immediately type the two **noise** lines to prove it's not trigger-happy:

> **lol same**
> **the build is green**

No reaction. **Say:** *"And it ignores the noise. False positives are worse than misses."*

> Don't cut this — restraint is the feature. An agent that fires on everything gets muted.

---

## 0:15–0:45 — The nudge

Run:

```
/looseends check
```

*(Runs the same overdue/stale check the scheduler runs on its own every 2 minutes — this
just does it now instead of waiting for the next tick. The seeded Q3 deck is genuinely
overdue, so it genuinely fires. Nothing is faked to make this happen.)*

A DM card arrives: **"⏰ Still on the hook — send the Q3 deck · overdue by 3h"**
with **Done / Snooze / Reassign / Escalate**.

Click **😴 Snooze → Tomorrow**. The card updates live.

**Say:** *"A private nudge — never a public call-out. Human in the loop: one click to
resolve it, snooze it, or hand it off."*

---

## 0:45–1:15 — Escalate = a real action

On the **unanswered question** card, click **📌 Escalate**.

**Cut to the MCP server terminal** — you'll see the `create_ticket` tool call land.
Cut back: the card now reads **"📌 Escalated → `LE-1` · created via the MCP connector"**.

**Say:** *"One click turns a forgotten Slack promise into a tracked ticket — through our
own open-source MCP server. Swap the mock connector for real Jira or Linear and the Slack
app doesn't change a line."*

---

## 1:15–1:45 — The dashboard

Open the **Loose Ends → Home** tab.

Overdue / Upcoming / Unanswered questions / Recently done — every loose end you own, each
with the same buttons. Point out the item you just escalated has moved to done.

**Say:** *"Everything you're on the hook for, in one place."*

---

## 1:45–2:20 — RTS query

Run:

```
/looseends ask what did I commit to this week?
```

A grounded answer comes back with **source permalinks** into the real conversations, and
the footer: *"🔎 Grounded with Slack Real-Time Search · N messages searched."*

**Say:** *"This is Slack's Real-Time Search API — the answer is grounded in what was
actually said in the workspace, with citations. Not a guess."*

---

## 2:20–3:00 — Why it matters + what's next

**Say, over the dashboard:**

*"Every team drops balls — not because people don't care, but because promises live in
chat and chat scrolls away. Loose Ends is the accountability layer: it uses Slack AI to
understand what was promised, Real-Time Search to ground it in real conversation, and MCP
to turn it into tracked work. Next: real Jira and Linear connectors, and a Marketplace
listing so any team can install it."*

End on the app name / logo.

---

## Emergency fallbacks (if something breaks on camera)

| If this breaks | Do this |
|---|---|
| MCP server is down → Escalate shows a warning | It's designed to fail soft. Restart terminal A, click again. |
| RTS returns an error | `/looseends ask` still answers from the DB and *says so* in the footer. Keep going — it's honest, not broken. |
| A nudge doesn't fire | `/looseends check` forces it. |
| Extractor misses a message | Re-post with a clearer commitment ("I'll send X by Friday"). It's tuned conservative on purpose. |
| Duplicate/ghost behavior | You have two app instances running. Kill all, start ONE. |

## Do NOT

- **Say plainly that the ticket store is local.** The ref is deliberately *not* a hyperlink,
  because this connector writes to `mcp-server/tickets.json`, not a real tracker — a link
  that 404s would be worse than no link. Set `TICKET_BASE_URL` to a real Jira/Linear
  instance and the ref becomes clickable everywhere, with no change to the Slack app.
  Cut to the MCP server terminal: that's the real tool call, and it's the honest proof.
- Don't run two app instances (dual Socket Mode connections split events).
- Don't skip the seed step — stale items will nudge you mid-take.
- Don't show `.env` on screen. **Your tokens are in it.**
