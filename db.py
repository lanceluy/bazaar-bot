"""SQLite storage: merchants, drafts, send log, suppression list."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import config

STATUSES = ("found", "drafted", "approved", "sent", "failed", "skipped")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS merchants (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                category     TEXT,
                website      TEXT,
                email        TEXT,
                place_id     TEXT UNIQUE,
                source_query TEXT,
                status       TEXT NOT NULL DEFAULT 'found',
                created_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS drafts (
                merchant_id INTEGER PRIMARY KEY REFERENCES merchants(id) ON DELETE CASCADE,
                subject     TEXT NOT NULL,
                body        TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS send_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id INTEGER REFERENCES merchants(id) ON DELETE CASCADE,
                sent_at     TEXT NOT NULL,
                result      TEXT NOT NULL,
                error       TEXT
            );

            CREATE TABLE IF NOT EXISTS suppression (
                email    TEXT PRIMARY KEY,
                reason   TEXT,
                added_at TEXT NOT NULL
            );
            """
        )


# ---- merchants -------------------------------------------------------------

def upsert_merchant(name, category, website, email, place_id, source_query):
    """Insert a merchant unless its place_id already exists. Returns (id, created)."""
    with get_conn() as conn:
        if place_id:
            row = conn.execute(
                "SELECT id FROM merchants WHERE place_id = ?", (place_id,)
            ).fetchone()
            if row:
                return row["id"], False
        cur = conn.execute(
            """INSERT INTO merchants
               (name, category, website, email, place_id, source_query, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'found', ?)""",
            (name, category, website, email, place_id, source_query, _now()),
        )
        return cur.lastrowid, True


def get_merchant(merchant_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM merchants WHERE id = ?", (merchant_id,)
        ).fetchone()


def list_merchants(status=None):
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM merchants WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM merchants ORDER BY created_at DESC"
            ).fetchall()
        return rows


def set_status(merchant_id, status):
    if status not in STATUSES:
        raise ValueError(f"invalid status {status!r}")
    with get_conn() as conn:
        conn.execute(
            "UPDATE merchants SET status = ? WHERE id = ?", (status, merchant_id)
        )


def set_email(merchant_id, email):
    with get_conn() as conn:
        conn.execute(
            "UPDATE merchants SET email = ? WHERE id = ?", (email, merchant_id)
        )


def status_counts():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM merchants GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}


# ---- drafts ----------------------------------------------------------------

def save_draft(merchant_id, subject, body):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO drafts (merchant_id, subject, body, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(merchant_id) DO UPDATE SET
                 subject = excluded.subject,
                 body = excluded.body,
                 updated_at = excluded.updated_at""",
            (merchant_id, subject, body, _now()),
        )


def get_draft(merchant_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM drafts WHERE merchant_id = ?", (merchant_id,)
        ).fetchone()


# ---- send log --------------------------------------------------------------

def log_send(merchant_id, result, error=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO send_log (merchant_id, sent_at, result, error) VALUES (?, ?, ?, ?)",
            (merchant_id, _now(), result, error),
        )


def recent_sends(limit=50):
    with get_conn() as conn:
        return conn.execute(
            """SELECT s.*, m.name AS merchant_name, m.email AS merchant_email
               FROM send_log s LEFT JOIN merchants m ON m.id = s.merchant_id
               ORDER BY s.sent_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()


# ---- suppression -----------------------------------------------------------

def add_suppression(email, reason="manual"):
    email = (email or "").strip().lower()
    if not email:
        return
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO suppression (email, reason, added_at) VALUES (?, ?, ?)
               ON CONFLICT(email) DO NOTHING""",
            (email, reason, _now()),
        )


def is_suppressed(email):
    email = (email or "").strip().lower()
    if not email:
        return False
    with get_conn() as conn:
        return (
            conn.execute(
                "SELECT 1 FROM suppression WHERE email = ?", (email,)
            ).fetchone()
            is not None
        )


def list_suppression():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM suppression ORDER BY added_at DESC"
        ).fetchall()
