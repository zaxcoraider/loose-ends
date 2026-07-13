"""Loose Ends — persistence layer (stdlib sqlite3).

Single file-based DB (loose_ends.sqlite). Thread-safe enough for our use:
one connection with check_same_thread=False + a module lock around writes,
since the Bolt handlers and the APScheduler thread both touch it.
"""
import os
import sqlite3
import threading
import time
import uuid

# Importing config is what loads .env. Without this, `LOOSEENDS_DB` is only visible to
# modules that happen to import config first, so a caller with a different import order
# silently opens a different database — no error, just the wrong data.
from . import config  # noqa: F401  (imported for the .env load, not for a name)

DB_PATH = os.environ.get("LOOSEENDS_DB", "loose_ends.sqlite")

_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row


def _now_ms() -> int:
    return int(time.time() * 1000)


def init_db() -> None:
    """Create the loose_ends table + indexes if they don't exist."""
    with _lock:
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS loose_ends (
                id             TEXT PRIMARY KEY,
                type           TEXT NOT NULL,          -- commitment | unanswered_question
                owner_user_id  TEXT NOT NULL,
                channel_id     TEXT NOT NULL,
                message_ts     TEXT NOT NULL,
                thread_ts      TEXT,
                summary        TEXT NOT NULL,
                due_at         INTEGER,                -- epoch ms, nullable
                status         TEXT NOT NULL DEFAULT 'open',
                confidence     REAL NOT NULL DEFAULT 0,
                created_at     INTEGER NOT NULL,
                updated_at     INTEGER NOT NULL,
                ticket_ref     TEXT,
                nudged_at      INTEGER                 -- epoch ms of last nudge (anti-spam)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_loose_ends_message_ts
                ON loose_ends(message_ts);
            CREATE INDEX IF NOT EXISTS idx_loose_ends_status ON loose_ends(status);
            CREATE INDEX IF NOT EXISTS idx_loose_ends_owner  ON loose_ends(owner_user_id);
            """
        )
        _conn.commit()


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


# ── writes ───────────────────────────────────────────────────────
def create_loose_end(obj: dict) -> dict | None:
    """Insert a loose end. Returns the stored row, or None if a row for the
    same message_ts already exists (de-dup via the unique index)."""
    now = _now_ms()
    row = {
        "id": obj.get("id") or str(uuid.uuid4()),
        "type": obj["type"],
        "owner_user_id": obj["owner_user_id"],
        "channel_id": obj["channel_id"],
        "message_ts": obj["message_ts"],
        "thread_ts": obj.get("thread_ts"),
        "summary": obj["summary"],
        "due_at": obj.get("due_at"),
        "status": obj.get("status", "open"),
        "confidence": obj.get("confidence", 0.0),
        "created_at": now,
        "updated_at": now,
        "ticket_ref": obj.get("ticket_ref"),
        "nudged_at": obj.get("nudged_at"),
    }
    with _lock:
        try:
            _conn.execute(
                """INSERT INTO loose_ends
                   (id, type, owner_user_id, channel_id, message_ts, thread_ts,
                    summary, due_at, status, confidence, created_at, updated_at,
                    ticket_ref, nudged_at)
                   VALUES
                   (:id, :type, :owner_user_id, :channel_id, :message_ts, :thread_ts,
                    :summary, :due_at, :status, :confidence, :created_at, :updated_at,
                    :ticket_ref, :nudged_at)""",
                row,
            )
            _conn.commit()
        except sqlite3.IntegrityError:
            return None  # duplicate message_ts
    return row


def _update(id: str, fields: dict) -> dict | None:
    fields = {**fields, "updated_at": _now_ms()}
    cols = ", ".join(f"{k} = :{k}" for k in fields)
    with _lock:
        _conn.execute(
            f"UPDATE loose_ends SET {cols} WHERE id = :id",
            {**fields, "id": id},
        )
        _conn.commit()
    return get_by_id(id)


def update_status(id: str, status: str, extra: dict | None = None) -> dict | None:
    return _update(id, {"status": status, **(extra or {})})


def set_due(id: str, due_at: int | None) -> dict | None:
    return _update(id, {"due_at": due_at})


def reassign(id: str, new_owner_id: str) -> dict | None:
    # clear the nudge clock so the new owner gets pinged on the next tick
    return _update(
        id,
        {"owner_user_id": new_owner_id, "status": "reassigned", "nudged_at": None},
    )


def set_ticket_ref(id: str, ref: str) -> dict | None:
    return _update(id, {"ticket_ref": ref})


def set_nudged(id: str, ts: int | None = None) -> dict | None:
    return _update(id, {"nudged_at": ts if ts is not None else _now_ms()})


# ── reads ────────────────────────────────────────────────────────
def get_by_id(id: str) -> dict | None:
    with _lock:
        cur = _conn.execute("SELECT * FROM loose_ends WHERE id = ?", (id,))
        return _row_to_dict(cur.fetchone())


def get_by_message_ts(message_ts: str) -> dict | None:
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM loose_ends WHERE message_ts = ?", (message_ts,)
        )
        return _row_to_dict(cur.fetchone())


def list_by_status(status: str) -> list[dict]:
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM loose_ends WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
        return [dict(r) for r in cur.fetchall()]


def list_by_owner(user_id: str) -> list[dict]:
    with _lock:
        cur = _conn.execute(
            "SELECT * FROM loose_ends WHERE owner_user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def list_open() -> list[dict]:
    return list_by_status("open")


_ACTIVE = ("open", "snoozed", "reassigned")


def list_due_commitments(now_ms: int, renudge_cutoff_ms: int) -> list[dict]:
    """Active commitments whose due time has passed and that aren't in the
    anti-spam cooldown (nudged_at older than the cutoff, or never nudged)."""
    q = f"""
        SELECT * FROM loose_ends
        WHERE type = 'commitment'
          AND status IN ({','.join('?' * len(_ACTIVE))})
          AND due_at IS NOT NULL AND due_at <= ?
          AND (nudged_at IS NULL OR nudged_at <= ?)
        ORDER BY due_at ASC
    """
    with _lock:
        cur = _conn.execute(q, (*_ACTIVE, now_ms, renudge_cutoff_ms))
        return [dict(r) for r in cur.fetchall()]


def list_stale_questions(created_before_ms: int, renudge_cutoff_ms: int) -> list[dict]:
    """Active questions older than the staleness window, not in cooldown."""
    q = f"""
        SELECT * FROM loose_ends
        WHERE type = 'unanswered_question'
          AND status IN ({','.join('?' * len(_ACTIVE))})
          AND created_at <= ?
          AND (nudged_at IS NULL OR nudged_at <= ?)
        ORDER BY created_at ASC
    """
    with _lock:
        cur = _conn.execute(q, (*_ACTIVE, created_before_ms, renudge_cutoff_ms))
        return [dict(r) for r in cur.fetchall()]


# initialize on import so callers never forget
init_db()
