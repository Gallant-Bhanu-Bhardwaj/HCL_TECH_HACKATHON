"""db.py - opens the SQLite database and reads settings."""
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "data/ujjwal.db")


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row      # rows can be read like dicts: row["name"]
    return con


def get_setting(name, when):
    """Value of a setting on a date: the newest row that has already taken effect.
    when is a date, a datetime or an ISO string; only the date part is used."""
    with connect() as con:
        row = con.execute(
            "SELECT value, source_doc FROM settings WHERE name = ? AND effective_from <= ? "
            "ORDER BY effective_from DESC LIMIT 1", (name, str(when)[:10])).fetchone()
    return (row["value"], row["source_doc"]) if row else (None, None)
