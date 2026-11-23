"""SQLite helpers. The DB path is read at call time so tests can point to a temp file."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS attendees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    organization TEXT NOT NULL,
    contact_number TEXT NOT NULL,
    ticket_token TEXT NOT NULL UNIQUE,
    qr_path TEXT,
    email_status TEXT DEFAULT 'pending',
    status TEXT DEFAULT 'Registered',
    registered_at TEXT,
    checked_in_at TEXT
)
"""


def db_path():
    return os.environ.get("DB_PATH", os.path.join("data", "event.db"))


@contextmanager
def connect():
    path = db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:  # commit / rollback
            yield conn
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.execute(SCHEMA)


def now():
    return datetime.now().isoformat(timespec="seconds")


def add_attendee(name, email, org, contact, token):
    """Insert a row. Raises sqlite3.IntegrityError if the email already exists."""
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO attendees (full_name, email, organization, contact_number,"
            " ticket_token, registered_at) VALUES (?,?,?,?,?,?)",
            (name, email, org, contact, token, now()),
        )
        return cur.lastrowid


def get_attendee(att_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM attendees WHERE id=?", (att_id,)).fetchone()


def get_by_token(token):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM attendees WHERE ticket_token=?", (token,)
        ).fetchone()


def list_attendees():
    with connect() as conn:
        return conn.execute("SELECT * FROM attendees ORDER BY id").fetchall()


def set_qr_path(att_id, path):
    with connect() as conn:
        conn.execute("UPDATE attendees SET qr_path=? WHERE id=?", (path, att_id))


def set_email_status(att_id, status):
    with connect() as conn:
        conn.execute("UPDATE attendees SET email_status=? WHERE id=?", (status, att_id))


def reset_checkins():
    """Set every attendee back to 'Registered'. Returns how many rows changed."""
    with connect() as conn:
        return conn.execute(
            "UPDATE attendees SET status='Registered', checked_in_at=NULL "
            "WHERE status!='Registered'"
        ).rowcount


def delete_all():
    """Remove every attendee (frees their emails to register again). Returns the count."""
    with connect() as conn:
        n = conn.execute("DELETE FROM attendees").rowcount
        conn.execute("DELETE FROM sqlite_sequence WHERE name='attendees'")
        return n


def check_in(token):
    """Returns ('ok'|'already'|'invalid', row). Atomic: only one scan can flip the status."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE attendees SET status='Checked In', checked_in_at=? "
            "WHERE ticket_token=? AND status='Registered'",
            (now(), token),
        )
        row = conn.execute(
            "SELECT * FROM attendees WHERE ticket_token=?", (token,)
        ).fetchone()
    if row is None:
        return "invalid", None
    return ("ok" if cur.rowcount == 1 else "already"), row
