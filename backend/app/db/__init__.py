"""Database package for FinAlly."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.db.schema import SCHEMA_SQL
from app.db.seed import SEED_SQL


# Database file path
DB_PATH = Path(__file__).parent.parent.parent / "db" / "finally.db"


class Database:
    """Thread-safe SQLite database connection manager."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._local = threading.local()
            self._initialized = True

    @contextmanager
    def get_connection(self):
        """Get a thread-local database connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row  # Return dict-like rows
        yield self._local.conn

    def init_db(self) -> None:
        """Initialize the database with schema and seed data.

        This is called on first request if the database doesn't exist or is empty.
        """
        # Create database directory if it doesn't exist
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            # Check if database needs initialization
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            if not tables:
                # Empty database - create schema and seed
                conn.executescript(SCHEMA_SQL)
                conn.executescript(SEED_SQL)
                conn.commit()
                print("[OK] Database initialized with schema and seed data")
            else:
                print("[OK] Database already initialized")


# Global database instance
db = Database()


def get_db() -> Database:
    """Dependency injection helper for FastAPI."""
    return db
