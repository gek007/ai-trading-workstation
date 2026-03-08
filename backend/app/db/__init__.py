"""Database package for FinAlly."""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from app.db.schema import REQUIRED_TABLES, SCHEMA_SQL
from app.db.seed import SEED_SQL

# Database file path — DB_PATH env var sets the directory (used in Docker).
# Falls back to <project-root>/db/finally.db for local development.
_db_dir = os.environ.get("DB_PATH")
if _db_dir:
    DB_PATH = Path(_db_dir) / "finally.db"
else:
    DB_PATH = Path(__file__).parent.parent.parent / "db" / "finally.db"


class Database:
    """Thread-safe SQLite database connection manager (singleton)."""

    _instance: Database | None = None
    _lock = threading.Lock()

    def __new__(cls) -> Database:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self._local = threading.local()
            self._initialized = True

    @contextmanager
    def get_connection(self):  # type: ignore[override]
        """Yield a thread-local database connection with dict-like rows."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA foreign_keys = ON")
        yield self._local.conn

    def init_db(self) -> None:
        """Initialize the database with schema and seed data if needed.

        Safe to call multiple times (idempotent).  Checks that ALL required
        tables exist — a partially-initialised DB is treated as empty.
        """
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            existing: set[str] = {row[0] for row in cursor.fetchall()}
            missing = REQUIRED_TABLES - existing

            if missing:
                conn.executescript(SCHEMA_SQL)
                print("[DB] Schema created")

            # Always run seed to ensure required rows exist (idempotent via INSERT OR IGNORE)
            conn.executescript(SEED_SQL)
            conn.commit()
            print("[DB] Schema already up-to-date")


# Global singleton
db = Database()


def get_db() -> Database:
    """FastAPI dependency — returns the global Database instance."""
    return db
