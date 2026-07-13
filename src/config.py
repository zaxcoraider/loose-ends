"""Central config: loads .env once and exposes typed settings."""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Slack ────────────────────────────────────────────────────────
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
SLACK_USER_TOKEN = os.environ.get("SLACK_USER_TOKEN", "")  # optional (RTS, Phase 8)

# ── DGrid (OpenAI-compatible AI gateway) ─────────────────────────
DGRID_API_KEY = os.environ.get("DGRID_API_KEY", "")
DGRID_BASE_URL = os.environ.get("DGRID_BASE_URL", "https://api.dgrid.ai/v1")
DGRID_MODEL = os.environ.get("DGRID_MODEL", "anthropic/claude-sonnet-4.6")

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
