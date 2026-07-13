"""Convert a fuzzy due-hint phrase + the message time into an epoch-ms due_at.

Deliberately small and rule-based (no LLM round-trip): handles the common Slack
phrasings. Returns None when the hint is unknown — the caller treats a commitment
with no due date as "nudge-on-next-tick / soft" rather than guessing wrong.

All times are computed in the message's local frame using the provided
`message_epoch_ms` as "now". Business EOD = 18:00, end of week = Friday 18:00.
"""
import re

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

EOD_HOUR = 18  # 6pm local == "end of day"

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


def _at(dt: datetime, hour: int) -> datetime:
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0)


def _next_weekday(base: datetime, target_wd: int) -> datetime:
    """The next occurrence of target weekday at EOD (today if it matches and still future-ish)."""
    days_ahead = (target_wd - base.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 0  # today
    return _at(base + timedelta(days=days_ahead), EOD_HOUR)


def parse_due(due_hint: str | None, message_epoch_ms: int) -> int | None:
    """Return an epoch-ms due timestamp, or None if the hint can't be resolved."""
    if not due_hint:
        return None
    h = due_hint.strip().lower()
    now = datetime.fromtimestamp(message_epoch_ms / 1000)

    # explicit "in N hours/minutes/days"
    m = re.search(r"in\s+(\d+)\s*(hour|hr|minute|min|day)s?", h)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit in ("hour", "hr"):
            return int((now + timedelta(hours=n)).timestamp() * 1000)
        if unit in ("minute", "min"):
            return int((now + timedelta(minutes=n)).timestamp() * 1000)
        if unit == "day":
            return int(_at(now + timedelta(days=n), EOD_HOUR).timestamp() * 1000)

    def ms(dt: datetime) -> int:
        return int(dt.timestamp() * 1000)

    # keyword phrases (order matters: check multi-word first)
    if "end of week" in h or "eow" in h or "this week" in h:
        return ms(_next_weekday(now, 4))  # Friday EOD
    if "next week" in h:
        return ms(_at(now + timedelta(days=7), EOD_HOUR))
    if "tonight" in h or "this evening" in h:
        return ms(_at(now, 21))  # 9pm
    if "tomorrow" in h:
        return ms(_at(now + timedelta(days=1), EOD_HOUR))
    if "today" in h or "eod" in h or "end of day" in h or "by cob" in h or "cob" in h:
        return ms(_at(now, EOD_HOUR))
    if "asap" in h or "right now" in h or "now" == h:
        return ms(now + timedelta(minutes=30))
    if "next month" in h:
        return ms(_at(now + relativedelta(months=1), EOD_HOUR))

    # a bare weekday name -> next occurrence
    for name, wd in _WEEKDAYS.items():
        if re.search(rf"\b{name}\b", h):
            return ms(_next_weekday(now, wd))

    return None
