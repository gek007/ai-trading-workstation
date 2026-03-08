"""Tests for database schema definition."""

from __future__ import annotations

import sqlite3


class TestDatabaseSchema:
    """Unit tests for database schema SQL."""

    def test_schema_sql_is_valid(self):
        """Test that schema SQL can be executed without errors."""
        from app.db.schema import SCHEMA_SQL

        # Create an in-memory database
        conn = sqlite3.connect(":memory:")

        # Execute schema
        conn.executescript(SCHEMA_SQL)

        # Verify tables were created
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        # Expected tables (sqlite_* are internal)
        expected_tables = [
            "chat_messages",
            "positions",
            "trades",
            "users_profile",
            "watchlist",
        ]
        for table in expected_tables:
            assert table in tables, f"Table {table} was not created"

        conn.close()

    def test_users_profile_table_structure(self):
        """Test users_profile table has correct columns and constraints."""
        from app.db.schema import SCHEMA_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        cursor = conn.cursor()

        # Get table structure
        cursor.execute("PRAGMA table_info(users_profile)")
        columns = {row[1]: row for row in cursor.fetchall()}

        # Verify columns exist
        assert "id" in columns
        assert columns["id"][2] == "TEXT"  # type
        assert columns["id"][5] == 1  # primary key

        assert "cash_balance" in columns
        assert columns["cash_balance"][2] in ("REAL", "FLOAT")  # SQLite may report as FLOAT
        assert columns["cash_balance"][3] == 1  # not null

        assert "created_at" in columns
        assert columns["created_at"][2] == "TEXT"
        assert columns["created_at"][3] == 1  # not null

        conn.close()

    def test_watchlist_table_structure(self):
        """Test watchlist table has correct columns and constraints."""
        from app.db.schema import SCHEMA_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        cursor = conn.cursor()

        # Get table structure
        cursor.execute("PRAGMA table_info(watchlist)")
        columns = {row[1]: row for row in cursor.fetchall()}

        # Verify columns
        assert "id" in columns
        assert columns["id"][5] == 1  # primary key

        assert "user_id" in columns
        assert columns["user_id"][2] == "TEXT"
        assert columns["user_id"][3] == 1  # not null
        assert columns["user_id"][4] == "'default'"  # default value

        assert "ticker" in columns
        assert columns["ticker"][2] == "TEXT"
        assert columns["ticker"][3] == 1  # not null

        assert "added_at" in columns
        assert columns["added_at"][2] == "TEXT"
        assert columns["added_at"][3] == 1  # not null

        # Verify unique constraint
        cursor.execute("PRAGMA index_list(watchlist)")
        indexes = cursor.fetchall()
        unique_indexes = [idx for idx in indexes if idx[2] == 1]  # unique
        assert len(unique_indexes) >= 1, "Watchlist should have unique constraint"

        conn.close()

    def test_positions_table_structure(self):
        """Test positions table has correct columns and constraints."""
        from app.db.schema import SCHEMA_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        cursor = conn.cursor()

        # Get table structure
        cursor.execute("PRAGMA table_info(positions)")
        columns = {row[1]: row for row in cursor.fetchall()}

        # Verify columns
        assert "id" in columns
        assert columns["id"][5] == 1  # primary key

        assert "user_id" in columns
        assert columns["user_id"][4] == "'default'"  # default value

        assert "ticker" in columns
        assert "quantity" in columns
        assert "avg_cost" in columns
        assert "updated_at" in columns

        conn.close()

    def test_trades_table_structure(self):
        """Test trades table has correct columns and constraints."""
        from app.db.schema import SCHEMA_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        cursor = conn.cursor()

        # Get table structure
        cursor.execute("PRAGMA table_info(trades)")
        columns = {row[1]: row for row in cursor.fetchall()}

        # Verify columns
        assert "id" in columns
        assert "user_id" in columns
        assert "ticker" in columns
        assert "side" in columns

        # Verify side has CHECK constraint
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='trades'")
        table_sql = cursor.fetchone()[0]
        assert "CHECK(side IN ('buy', 'sell'))" in table_sql

        assert "quantity" in columns
        assert "price" in columns
        assert "executed_at" in columns

        conn.close()

    def test_chat_messages_table_structure(self):
        """Test chat_messages table has correct columns and constraints."""
        from app.db.schema import SCHEMA_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        cursor = conn.cursor()

        # Get table structure
        cursor.execute("PRAGMA table_info(chat_messages)")
        columns = {row[1]: row for row in cursor.fetchall()}

        # Verify columns
        assert "id" in columns
        assert "user_id" in columns
        assert "role" in columns

        # Verify role has CHECK constraint
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='chat_messages'")
        table_sql = cursor.fetchone()[0]
        assert "CHECK(role IN ('user', 'assistant'))" in table_sql

        assert "content" in columns
        assert "actions" in columns
        assert "created_at" in columns

        conn.close()

    def test_foreign_keys_are_enabled(self):
        """Test that foreign keys are enabled in schema."""
        from app.db.schema import SCHEMA_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        cursor = conn.cursor()

        # Check if foreign keys are enabled
        cursor.execute("PRAGMA foreign_keys")
        is_enabled = cursor.fetchone()[0]

        assert is_enabled == 1, "Foreign keys should be enabled"

        conn.close()

    def test_indexes_are_created(self):
        """Test that performance indexes are created."""
        from app.db.schema import SCHEMA_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' ORDER BY name"
        )
        indexes = [row[0] for row in cursor.fetchall()]

        expected_indexes = [
            "idx_chat_user_created",  # compound index replaces two separate ones
            "idx_positions_user",
            "idx_trades_ticker",
            "idx_trades_user",
            "idx_watchlist_user",
        ]

        for index in expected_indexes:
            assert index in indexes, f"Index {index} was not created"

        conn.close()

    def test_required_tables_constant(self):
        """Test that REQUIRED_TABLES lists all five application tables."""
        from app.db.schema import REQUIRED_TABLES

        assert REQUIRED_TABLES == {
            "users_profile",
            "watchlist",
            "positions",
            "trades",
            "chat_messages",
        }

    def test_schema_constants_are_defined(self):
        """Test that SCHEMA_SQL constant is defined and non-empty."""
        from app.db.schema import SCHEMA_SQL

        assert SCHEMA_SQL is not None
        assert len(SCHEMA_SQL) > 0
        assert "CREATE TABLE" in SCHEMA_SQL
        assert "users_profile" in SCHEMA_SQL
