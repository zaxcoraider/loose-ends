# Slack Marketplace readiness — where Loose Ends actually stands

What a Marketplace listing requires, and honestly where this app falls short today.
Written as a post-hackathon roadmap, not a checklist to rush.

**Bottom line:** the app is not *close*. One requirement is disqualifying on its own
(Socket Mode), and another can't be engineered at all (5 active workspaces). Everything
else is real work on the delivery layer, not the product.

---

## Hard blockers

### 1. Socket Mode is not allowed on the Marketplace

> "If you intend to submit your app to be available for use in the Slack Marketplace,
> using HTTP is a requirement."

Loose Ends is Socket Mode end to end — that was the *right* call for building solo with no
public URL, and it's why the app works at all. But a listed app must serve a **public HTTPS
Request URL** for events and interactivity. That means hosting: a real server, TLS 1.2+,
request signing via the signing secret, and an uptime commitment.

*This alone makes a listing impossible without re-hosting the app.*

### 2. Five active workspaces

> "at least 5 active workspace installs before you can submit" — active meaning used in the
> past 28 days, **sandboxes don't count**.

This is adoption, not engineering. Five real teams have to install and *use* it for a month.
No amount of code closes this gap, and the 28-day window means the clock can't be started
retroactively.

---

## The rebuild a listing implies

Today the app is **single-tenant**: one bot token in `.env`, one local SQLite file, one
loopback MCP server. A Marketplace app is **multi-tenant**. Concretely:

| Area | Today | Needed |
|---|---|---|
| Event delivery | Socket Mode | Public HTTPS endpoint, request signing, TLS 1.2+ |
| Install | Tokens pasted into `.env` | OAuth v2 flow with the `state` parameter, "Add to Slack" button |
| Tokens | Plaintext in `.env` | Encrypted per-workspace token store; never logged, never in the repo |
| Storage | `loose_ends.sqlite` on disk | Hosted DB, rows scoped by `team_id` |
| MCP server | `127.0.0.1`, no auth | Authenticated connector (already flagged in the README) |
| Scheduler | In-process APScheduler | Survives restarts; per-workspace |

## Scope justification

Marketplace review applies least-privilege and specifically scrutinises `*:history` scopes
and search scopes. Loose Ends requests `channels:history`, `groups:history`, `im:history`,
and the user scope `search:read.public`. Every one of those is defensible — reading channel
history *is* the product — but each needs a written justification, and broad history access
invites the deepest form of review.

## The privacy story is the real conversation

Reviewers will land on the disclosure already in `README.md`: every qualifying message in an
invited channel is sent to a **third-party LLM gateway** for classification. That's honest,
and it's exactly what a security review exists to examine. A listing needs:

- The gateway named as a **subprocessor** in the privacy policy — what's sent, why, retention.
- Ideally, **self-hosting the model** so no third party sees customer messages. `src/llm.py`
  is already a thin wrapper — repoint `DGRID_BASE_URL` and nothing else changes. This is the
  single highest-leverage change for reviewability.
- Rate limiting (today: one LLM call per qualifying message, unbounded).

## Listing collateral (none of this exists yet)

- **Landing page** — public, no login/paywall, with an "Add to Slack" button, screenshots,
  and a post-install success state. A GitHub repo does **not** count.
- **Privacy policy** — collection, use, retention, deletion/access requests, contact method.
- **Support contact** — email or webform, publicly reachable, **2 business day** response.
- **Screenshots** — 1600×1000, under 2MB. (Note: `assets/architecture.png` is 1500×1010 —
  close, but it's a diagram, not an in-Slack screenshot. Both would be needed.)
- **Short description** — 10 words or fewer.
- **Icon** — done (`assets/logo-512.png`).
- **Demo video** — optional here, 30–90s, public YouTube, captions.

---

## If this becomes the goal

The product is the hard part and it's finished. What's missing is the *distribution* layer,
and it's in this order:

1. Re-host on HTTP (Bolt supports it — the handlers barely change; it's the app wiring).
2. OAuth v2 install + per-workspace token storage.
3. Multi-tenant datastore, `team_id` on every row.
4. Self-host the extraction model, or name the gateway as a subprocessor.
5. Auth the MCP connector.
6. Landing page, privacy policy, support.
7. Get five teams using it for 28 days.
8. *Then* submit.

Steps 1–6 are weeks, not days. Step 7 is months and isn't up to you.

## Sources

- [Marketplace guidelines & requirements](https://docs.slack.dev/slack-marketplace/slack-marketplace-app-guidelines-and-requirements/)
- [Comparing HTTP & Socket Mode](https://docs.slack.dev/apis/events-api/comparing-http-socket-mode/)
