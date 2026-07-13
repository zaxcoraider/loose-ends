# Loose Ends — 2-Minute Demo — Scene-by-Scene Recording Guide

Five scenes. **Problem → Solution → Walkthrough → Sponsor integration → Why it matters.**

For each scene you get: what to set up, exactly what to do on screen, and the **VO to read
word-for-word**. VO is written to ~150 words/min — the whole script is ~290 words, which
lands at **1:55–2:00**. Don't ad-lib; you'll overrun.

**Record picture first, voice second.** Do the clicks silently, get clean footage, then read
the VO over it. Trying to talk and drive at the same time is how takes die.

---

## Before you hit record

### 1. Reset to a clean, known state

```bash
.venv/Scripts/python.exe -u scripts/seed_demo.py
```

This wipes the DB and seeds three items so the dashboard looks alive from frame one:

| Item | State | Why it's there |
|---|---|---|
| send the Q3 deck | **overdue by 3h** | This is the one that nudges in Scene 3. It is *genuinely* overdue — nothing is faked. |
| share the roadmap doc | due in 6h | Fills the "Upcoming" group on the dashboard. |
| who's handling the prod deploy tonight? | stale, unanswered | This is the one you escalate in Scene 4. |

### 2. Widen the scheduler interval (recording only)

`.env` carries `CHECK_INTERVAL_MINUTES=30` for the take. The scheduler ships at 2 minutes,
and it genuinely fires on its own — which is exactly the problem while recording: if a tick
lands before you run `/looseends check`, it nudges the Q3 deck, the 4-hour re-nudge cooldown
kicks in, and Scene 3 shows **nothing** on camera. Widening the interval to 30 minutes means
no tick can land inside your take. `/looseends check` runs the identical `run_checks()` code
path, so nothing about the demo is faked — you're just choosing when it happens.

**Put this back to 2 (or delete the line) once the video is recorded.**

### 3. Start the two processes

```bash
# Terminal A — MCP server. KEEP THIS VISIBLE, you cut to it in Scene 4.
cd mcp-server && ../.venv/Scripts/python.exe -u server.py

# Terminal B — the app. ONE instance only.
.venv/Scripts/python.exe -u -m src.app
```

In terminal B, confirm two lines before you record:
`🔎 Real-Time Search: enabled` and `scheduler started (every 30.0 min)`.
If RTS says disabled, Scene 4's `/ask` falls back to the DB — still honest, still works, but
you lose the RTS beat.

### 4. Screen layout

- **Slack, full screen, on `#general`.** This is your main shot. Zoom Slack to ~110% so text is
  legible after compression.
- **Terminal A in a small window** you can bring forward for one cut in Scene 4. Second monitor
  is ideal; a floating window you `Alt+Tab` to also works.
- **Do Not Disturb on.** No email toasts, no calendar popups.
- Record **1080p**. Open on the product — no face cam, no title card, no "hi everyone".

---

# SCENE 1 — The problem · `0:00 – 0:18`

**Shot:** Slack `#general`, full screen.

**Do this:**
1. Click into the message box and type, at normal speed:
   > `I'll send the pricing one-pager to the client by Friday.`
2. Hit enter.
3. **Hold. Do nothing for ~3 seconds.** Loose Ends adds a 👀 reaction to your message. Let
   the viewer see it appear on its own.

**VO:**

> **"Everybody makes promises like this in Slack. And Slack forgets them — the promise lives
> in a message, and the message scrolls away. Three days later nobody has the one-pager.
> Every team drops balls this way. Not because people don't care, but because chat has
> no memory."**

> **Why this line, not the Q3 deck:** the Q3 deck is already seeded as overdue for Scene 3.
> Committing to something *different* on camera keeps the dashboard clean and proves the
> extractor is running live, not replaying a fixture.

---

# SCENE 2 — The solution · `0:18 – 0:32`

**Shot:** same. Stay in `#general`.

**Do this:**
1. Move your cursor to the 👀 reaction and let it rest there for a beat.
2. Now type the two noise lines and send them, one after the other:
   > `lol same`
   > `the build is green`
3. **Hold ~3 seconds.** Nothing happens. No reaction. That silence is the shot.

**VO:**

> **"Loose Ends just caught that promise. Nobody asked it to. And it ignores the noise —
> that's the whole trick. An agent that nags you about nothing gets muted on day one.
> False positives are worse than misses."**

> **Do not cut this scene for time.** Restraint is the feature. Judges have seen a hundred
> agents that fire on everything.

---

# SCENE 3 — The walkthrough · `0:32 – 1:10`

**Shot:** starts in `#general`, ends on the App Home tab.

**Do this:**
1. In the message box, run:
   ```
   /looseends check
   ```
   *(This runs the exact overdue/stale pass the scheduler runs on its own every two minutes.
   It just does it now instead of making the viewer wait for the next tick.)*
2. Two DM cards arrive from Loose Ends. **Click into the Loose Ends DM.** Both cards are
   there: the overdue **Q3 deck** commitment, and the stale **prod deploy** question.
3. On the **Q3 deck** card, click **😴 Snooze** → choose **Tomorrow**. The card updates in
   place — hold on it for a beat so the change is visible.
4. Click the **Loose Ends** app in the sidebar → open the **Home** tab. Sit on the dashboard.

**VO:**

> **"It watches for two things: promises people make, and questions nobody answered. When a
> promise goes overdue, or a question goes stale, it tells you — privately. Never a public
> call-out; nobody gets shamed in front of the team. And you're always in control: done,
> snooze, hand it off. Or see everything you're on the hook for in one place, sorted by what
> actually needs you next."**

---

# SCENE 4 — The sponsor integration · `1:10 – 1:45`

This is the scene the tech prize is won in. Two beats: **MCP**, then **RTS**.

**Shot A — MCP (`1:10 – 1:30`):**
1. Go back to the Loose Ends DM. Find the **unanswered question** card
   ("who's handling the prod deploy tonight?").
2. Click **📌 Escalate**. Confirm the dialog.
3. **CUT to Terminal A** — the MCP server. The `create_ticket` tool call lands on screen,
   live. Hold on it for ~2 seconds so it's readable.
4. **CUT back to Slack.** The card now reads **📌 Escalated → `LE-…`**.

**VO for Shot A:**

> **"Or escalate it. Watch — that's a tool call hitting our own MCP server. We didn't just
> plug into somebody else's; we built one and open-sourced it. A forgotten Slack promise is
> now a tracked ticket. Point that connector at real Jira or Linear and the Slack app doesn't
> change a line."**

**Shot B — RTS (`1:30 – 1:45`):**
1. Back in `#general`, run:
   ```
   /looseends ask what did I commit to this week?
   ```
2. The cited answer comes back. **Hover over one of the permalinks** so the viewer sees it
   points at a real message.

**VO for Shot B:**

> **"And this is Slack's Real-Time Search API. The answer is grounded in what was actually
> said in this workspace — with citations back to the real messages. Not a guess."**

---

# SCENE 5 — Why it matters · `1:45 – 2:00`

**Shot:** back on the App Home dashboard. Don't touch anything. Just let it sit.

**VO:**

> **"Every team already has a task tracker. Almost nothing promised in Slack ever reaches it.
> Loose Ends is the layer in between — it catches the work that lives and dies in chat, and
> it does it quietly enough that you'd actually leave it turned on."**

**Last frame:** cut to the logo (`assets/`) for ~1 second. End there. No outro, no thanks.

---

## Shot list (print this)

| # | Time | Screen | Action | Beat |
|---|---|---|---|---|
| 1 | 0:00 | Slack `#general` | Type the pricing one-pager promise | 👀 appears by itself |
| 2 | 0:18 | Slack `#general` | Type `lol same` / `the build is green` | Nothing happens |
| 3 | 0:32 | Slack → DM → Home | `/looseends check`, snooze the Q3 card, open Home | Card updates in place |
| 4a | 1:10 | DM → **Terminal A** → DM | Escalate the question, cut to MCP server | `create_ticket` lands live |
| 4b | 1:30 | Slack `#general` | `/looseends ask what did I commit to this week?` | Cited permalinks |
| 5 | 1:45 | App Home | Nothing. Hold. | Logo, out. |

---

## Say this, not that

| Don't say | Say |
|---|---|
| "It uses Slack AI" | **"An LLM extractor."** It's Claude behind an OpenAI-compatible gateway — *not* a Slack AI feature. You ship two of the three sponsor technologies (RTS + MCP); overclaiming the third buys nothing and costs credibility. |
| "It creates a Jira ticket" | **"A tracked ticket, through our MCP connector."** The tool call is real; the tracker is a mock that writes to a local file. Cutting to the terminal *is* the honest proof — it's stronger than the claim. |

## If something breaks on camera

| Breaks | Do |
|---|---|
| MCP server down → Escalate warns | It fails soft by design. Restart terminal A, click again. |
| RTS errors | `/ask` still answers from the DB **and says so in the footer**. Keep rolling — that's honest, not broken. |
| No nudge fires | `/looseends check` forces it. If still nothing, re-run `seed_demo.py`. |
| Extractor misses your live line | Re-post something blunter: *"I'll send X by Friday."* It's tuned conservative on purpose. |
| Two reactions / two cards | You have two app instances running. Kill all python, start exactly one. |
