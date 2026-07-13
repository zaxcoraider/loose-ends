"""Central config: loads .env once and exposes typed settings."""
import os
from dotenv import load_dotenv

# One process talks to exactly one workspace — a Socket Mode connection is bound to a
# single bot token. To run against a different workspace, point ENV_FILE at that
# workspace's env file rather than editing this one:
#
#     ENV_FILE=.env.looseend python -m src.app
#
# Give each env file its own LOOSEENDS_DB too, or the two workspaces write their loose
# ends into the same database and each dashboard shows the other's items.
load_dotenv(os.environ.get("ENV_FILE", ".env"))

# ── Slack ────────────────────────────────────────────────────────
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
SLACK_USER_TOKEN = os.environ.get("SLACK_USER_TOKEN", "")  # optional — Real-Time Search

# ── DGrid (OpenAI-compatible AI gateway) ─────────────────────────
DGRID_API_KEY = os.environ.get("DGRID_API_KEY", "")
DGRID_BASE_URL = os.environ.get("DGRID_BASE_URL", "https://api.dgrid.ai/v1")
DGRID_MODEL = os.environ.get("DGRID_MODEL", "anthropic/claude-sonnet-4.6")

# ── Ticketing ────────────────────────────────────────────────────
# Base URL of the tracker the MCP connector writes to (e.g. https://your.atlassian.net/browse).
# Left empty in the demo: the connector stores tickets locally, so we render the ref as
# plain text rather than linking to a host that doesn't exist.
TICKET_BASE_URL = os.environ.get("TICKET_BASE_URL", "").rstrip("/")

# ── Tuning ───────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.6"))
STALE_HOURS = float(os.environ.get("STALE_HOURS", "4"))
RENUDGE_HOURS = float(os.environ.get("RENUDGE_HOURS", "4"))  # anti-spam cooldown
CHECK_INTERVAL_MINUTES = float(os.environ.get("CHECK_INTERVAL_MINUTES", "2"))


def require(*names: str) -> None:
    """Raise a clear error if any required env var is missing."""
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise SystemExit(
            "Missing required env vars: "
            + ", ".join(missing)
            + "\nCopy .env.example to .env and fill them in."
        )
