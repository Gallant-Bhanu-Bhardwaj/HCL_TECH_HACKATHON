"""Reusable SQLite connection, schema/seed initialization (api-contracts
§4.6, architecture §6/§10). Raw `sqlite3` only — no ORM; the approved
stack (architecture §5/§10) never called for one.

Usage:
    from app.db.connection import init_db, get_connection

    # once, at app startup:
    conn = init_db()          # applies db/schema.sql + db/seed_data.sql
    conn.close()               # not kept open across requests

    # per request / per call, elsewhere:
    conn = get_connection()
    try:
        ...
    finally:
        conn.close()

`init_db()` is idempotent: calling it again against the same file is a
cheap no-op (it only applies schema.sql if no tables exist yet, and
only applies seed_data.sql if the data looks unseeded) — it does not
re-run or duplicate the seed. `db/seed_data.sql` itself is never
modified by this module.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from app.config import settings as default_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"
DEFAULT_SEED_PATH = REPO_ROOT / "db" / "seed_data.sql"

# Guards concurrent init_db() calls (e.g. two workers starting at once
# against the same file) from racing on the create-tables step.
_init_lock = threading.Lock()


def _resolve_path(db_path: str | None) -> str:
    return db_path if db_path is not None else default_settings.db_path


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a fresh connection to `db_path` (default: the configured
    DB_PATH, api-contracts §13) with foreign keys enforced on this
    connection (schema.sql's own PRAGMA only applies to the connection
    that runs it — every connection must set this itself).

    Cheap to call per request: SQLite connection setup is lightweight,
    and this does no schema/seed work — see init_db() for that.
    """
    conn = sqlite3.connect(_resolve_path(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _has_tables(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
    ).fetchone()
    return row[0] > 0


def _looks_seeded(conn: sqlite3.Connection) -> bool:
    """Cheap, safe-before-schema-exists marker: `stations` is the first
    table the seed populates and nothing else ever deletes from it."""
    try:
        row = conn.execute("SELECT COUNT(*) FROM stations").fetchone()
        return row[0] > 0
    except sqlite3.OperationalError:
        return False  # table doesn't exist yet -> definitely not seeded


def init_db(
    db_path: str | None = None,
    schema_path: Path | str = DEFAULT_SCHEMA_PATH,
    seed_path: Path | str | None = DEFAULT_SEED_PATH,
) -> sqlite3.Connection:
    """Initialize the database ONCE: create tables from `schema_path` if
    none exist, then load `seed_path` if the data doesn't look seeded
    yet. Call this once at process/app startup (app/main.py), never per
    request — repeated calls are safe (idempotent) but pointless.

    Returns a live connection to the now-initialized database; callers
    typically close it immediately and use get_connection() per request
    instead (this module does not hold a long-lived shared connection,
    which avoids SQLite's cross-thread/connection write-lock pitfalls).
    """
    path = _resolve_path(db_path)
    with _init_lock:
        conn = get_connection(path)
        try:
            if not _has_tables(conn):
                conn.executescript(Path(schema_path).read_text(encoding="utf-8"))
            if seed_path is not None and not _looks_seeded(conn):
                conn.executescript(Path(seed_path).read_text(encoding="utf-8"))
            conn.commit()
        except Exception:
            conn.close()
            raise
        return conn


def check_connectivity(db_path: str | None = None) -> bool:
    """Real DB connectivity check for GET /health (api-contracts §4.6).
    Touches no passenger data — a bare `SELECT 1`, nothing else."""
    try:
        conn = get_connection(db_path)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
        return True
    except sqlite3.Error:
        return False
