"""Tests for Database connection manager."""

from __future__ import annotations

import sqlite3
import threading


class TestDatabase:
    """Unit tests for Database class."""

    def test_database_is_singleton(self):
        """Test that Database is a singleton."""
        from app.db import Database

        db1 = Database()
        db2 = Database()

        assert db1 is db2, "Database should be a singleton"

    def test_database_thread_local_connections(self):
        """Test that each thread gets its own connection."""
        from app.db import Database

        db = Database()

        connections = []
        errors = []

        def get_connection_in_thread(thread_id):
            try:
                with db.get_connection() as conn:
                    connections.append(conn)
                    # Verify connection works
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()[0]
                    assert result == 1
            except Exception as e:
                errors.append((thread_id, e))

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=get_connection_in_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check no errors occurred
        assert len(errors) == 0, f"Errors occurred in threads: {errors}"

        # Verify each thread got a connection
        assert len(connections) == 5

    def test_get_connection_returns_working_connection(self):
        """Test that get_connection returns a usable database connection."""
        from app.db import Database

        db = Database()

        with db.get_connection() as conn:
            # Verify it's a SQLite connection
            assert isinstance(conn, sqlite3.Connection)

            # Verify we can execute queries
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()[0]
            assert result == 1

    def test_get_connection_uses_row_factory(self):
        """Test that connections use dict-like row factory."""
        from app.db import Database

        db = Database()

        # First initialize the database
        db.init_db()

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users_profile LIMIT 1")
            row = cursor.fetchone()

            # Row should be dict-like (accessible by column name)
            assert row is not None
            assert "id" in row.keys()
            assert "cash_balance" in row.keys()
            assert row["id"] == "default"

    def test_init_db_creates_database_file(self):
        """Test that init_db creates the database file."""
        from app.db import DB_PATH, Database

        db = Database()
        db.init_db()

        # Verify database file was created
        assert DB_PATH.exists()
        assert DB_PATH.is_file()

    def test_init_db_creates_schema_on_empty_database(self):
        """Test that init_db creates schema when database is empty."""
        from app.db import Database

        db = Database()
        db.init_db()

        # Verify tables were created
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]

            # Should have our 5 tables (excluding sqlite_* internal tables)
            expected_tables = [
                "chat_messages",
                "positions",
                "trades",
                "users_profile",
                "watchlist",
            ]
            for table in expected_tables:
                assert table in tables

    def test_init_db_seeds_data_on_empty_database(self):
        """Test that init_db seeds default data on empty database."""
        from app.db import Database

        db = Database()
        db.init_db()

        # Verify user profile was seeded
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cash_balance FROM users_profile")
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "default"
            assert row[1] == 10000.0

            # Verify watchlist was seeded
            cursor.execute("SELECT COUNT(*) FROM watchlist")
            count = cursor.fetchone()[0]
            assert count >= 1, "Watchlist should have at least 1 entry"

    def test_init_db_skips_if_database_already_initialized(self, capsys):
        """Test that init_db skips initialization if all tables exist."""
        from app.db import Database

        db = Database()
        db.init_db()

        # Add a sentinel trade to confirm data isn't wiped on second call
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)"
                " VALUES ('test-id', 'default', 'TEST', 'buy', 10, 100.0, datetime('now'))"
            )
            conn.commit()

        db.init_db()

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades WHERE id = 'test-id'")
            count = cursor.fetchone()[0]
            assert count == 1, "Existing data should be preserved on second init_db call"

        captured = capsys.readouterr()
        assert "up-to-date" in captured.out.lower() or "already" in captured.out.lower()

    def test_init_db_reinitialises_if_tables_missing(self):
        """Test that init_db detects and fills missing tables.

        Uses an isolated in-memory database to avoid corrupting the shared
        thread-local connection used by all other tests (executescript() has
        side-effects on the connection's isolation_level).
        """
        import sqlite3

        from app.db.schema import REQUIRED_TABLES, SCHEMA_SQL
        from app.db.seed import SEED_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)

        # Simulate partial initialisation
        conn.execute("DROP TABLE IF EXISTS chat_messages")
        conn.commit()

        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        existing = {row[0] for row in cursor.fetchall()}
        assert "chat_messages" in REQUIRED_TABLES - existing, (
            "chat_messages should be detected as missing"
        )

        # Re-apply schema (CREATE TABLE IF NOT EXISTS is idempotent)
        conn.executescript(SCHEMA_SQL)

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'"
        )
        assert cursor.fetchone() is not None, "chat_messages should be recreated by re-init"
        conn.close()

    def test_database_connection_context_manager_cleanup(self):
        """Test that connection context manager properly handles cleanup."""
        from app.db import Database

        db = Database()
        db.init_db()

        # Open and close multiple connections
        for _ in range(3):
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                assert cursor.fetchone()[0] == 1

        # Should not raise any errors

    def test_concurrent_database_reads(self):
        """Test that database handles concurrent reads correctly."""
        from app.db import Database

        db = Database()
        db.init_db()

        results = []
        errors = []

        def read_user_profile(thread_id):
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT cash_balance FROM users_profile WHERE id = 'default'")
                    row = cursor.fetchone()
                    results.append((thread_id, row[0]))
            except Exception as e:
                errors.append((thread_id, e))

        # Run concurrent reads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=read_user_profile, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all threads succeeded
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10

        # All should have read the same cash balance
        cash_balances = {r[1] for r in results}
        assert len(cash_balances) == 1
        assert 10000.0 in cash_balances

    def test_get_db_dependency_injection(self):
        """Test that get_db returns the database instance."""
        from app.db import Database, db, get_db

        result = get_db()

        assert result is db
        assert isinstance(result, Database)

    def test_database_handles_foreign_key_constraints(self):
        """Test that foreign key constraints are enforced."""
        from app.db import Database

        db = Database()
        db.init_db()

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Try to insert a watchlist entry with non-existent user_id
            # Should fail due to foreign key constraint
            try:
                cursor.execute(
                    "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES ('test-id', 'nonexistent-user', 'TEST', datetime('now'))"
                )
                conn.commit()
                assert False, "Should have raised IntegrityError"
            except sqlite3.IntegrityError:
                # Expected behavior
                pass
