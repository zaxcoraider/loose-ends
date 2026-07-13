"""Slack Real-Time Search (RTS) — `assistant.search.context`.

Optional enrichment layer. Loose Ends works fully without it: every function here
degrades to an empty result rather than raising, so a missing token, a plan without
Slack AI Search, or a transient API error can never break `/looseends ask` or a nudge.

Why a USER token (`xoxp-`), not the bot token: per the RTS docs, bot-token calls require
an `action_token`, which Slack only mints inside `message` / `app_mention` event payloads.
A slash command has no such token, so the bot token cannot search from `/looseends ask`.
A user token needs no action_token — and it correctly scopes results to channels the
asking user can already see.

Honesty rule: a `Result` reports what actually happened on THIS call. We never claim an
answer was "grounded with Real-Time Search" when the search in fact failed or was skipped.
"""
import logging
import time
from dataclasses import dataclass, field

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from . import config

log = logging.getLogger("looseends.rts")

# Errors meaning "RTS will never work as configured" — worth telling the user about,
# unlike transient failures (rate_limited, service_unavailable) which we just swallow.
_FATAL = {
    "missing_scope": "the user token is missing the `search:read.public` scope",
    "not_allowed_token_type": "a user token (`xoxp-`) is required, not a bot token",
    "assistant_search_context_disabled": "Real-Time Search is disabled for this workspace",
    "feature_not_enabled": "this workspace's plan doesn't include the search feature",
    "invalid_auth": "the user token is invalid or is still a placeholder",
    "token_expired": "the user token has expired",
    "token_revoked": "the user token was revoked",
    "no_permission": "the token lacks permission to search",
    "access_denied": "the workspace denied the search request",
}


@dataclass
class Result:
    """Outcome of one RTS attempt. `ok` means the API genuinely answered us."""
    hits: list[dict] = field(default_factory=list)
    ok: bool = False
    error: str | None = None       # raw Slack error code
    reason: str | None = None      # human explanation, for fatal errors

    def __bool__(self) -> bool:
        return bool(self.hits)


def _token() -> str:
    """The configured user token, ignoring the .env.example placeholder."""
    tok = (config.SLACK_USER_TOKEN or "").strip()
    if not tok.startswith("xoxp-") or "your-user" in tok or "your-us" in tok:
        return ""
    return tok


_client = WebClient(token=_token()) if _token() else None


def is_enabled() -> bool:
    """True if a plausible user token is configured (not whether it works)."""
    return _client is not None


def info() -> dict | None:
    """`assistant.search.info` — what can search actually do here? None on failure."""
    if not _client:
        return None
    try:
        return _client.api_call("assistant.search.info", http_verb="GET").data
    except SlackApiError as e:
        log.warning("rts info failed: %s", e.response.get("error"))
        return None
    except Exception as e:  # noqa: BLE001 — RTS must never break a caller
        log.warning("rts info failed: %s", e)
        return None


def search(
    query: str,
    *,
    limit: int = 10,
    days: int | None = 7,
    include_context_messages: bool = False,
) -> Result:
    """Search workspace messages for context. Returns a Result; never raises.

    Each hit: {author_name, author_user_id, channel_id, channel_name,
               message_ts, content, permalink, is_author_bot}
    """
    if not _client:
        return Result(ok=False, error="not_configured",
                      reason="no `SLACK_USER_TOKEN` is set")
    if not query.strip():
        return Result(ok=False, error="missing_query")

    body: dict = {
        "query": query,
        "content_types": ["messages"],
        "channel_types": ["public_channel"],  # matches the search:read.public scope
        "limit": max(1, min(limit, 20)),
        "sort": "score",
        "sort_dir": "desc",
        "include_context_messages": include_context_messages,
    }
    if days:
        body["after"] = int(time.time()) - days * 86400

    try:
        resp = _client.api_call("assistant.search.context", json=body)
        messages = (resp.data.get("results") or {}).get("messages") or []
    except SlackApiError as e:
        err = e.response.get("error", "unknown")
        reason = _FATAL.get(err)
        (log.error if reason else log.warning)(
            "RTS search failed (%s) — answering from tracked items only", err
        )
        return Result(ok=False, error=err, reason=reason)
    except Exception as e:  # noqa: BLE001
        log.warning("RTS search failed (%s) — answering from tracked items only", e)
        return Result(ok=False, error="exception", reason=str(e))

    # Drop our own nudge cards and other bot chatter: they'd just echo the DB back at us.
    return Result(hits=[m for m in messages if not m.get("is_author_bot")], ok=True)


def status_note(result: Result) -> str:
    """Footer line describing what actually grounded the answer. Always truthful."""
    if result.ok:
        n = len(result.hits)
        if n:
            return f"_🔎 Grounded with Slack Real-Time Search · {n} message(s) searched._"
        return "_🔎 Real-Time Search found no related messages — answered from tracked items._"
    if result.error == "not_configured":
        return ("_Real-Time Search is off — set `SLACK_USER_TOKEN` (scope "
                "`search:read.public`) to ground answers in workspace history._")
    if result.reason:
        return f"_Real-Time Search unavailable ({result.reason}) — answered from tracked items._"
    return "_Real-Time Search was unreachable — answered from tracked items._"
