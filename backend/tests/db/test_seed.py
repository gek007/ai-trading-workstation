"""Tests for database seed data."""

from __future__ import annotations

import sqlite3


class TestSeedData:
    """Unit tests for seed data SQL."""

    def test_seed_sql_is_valid(self):
        """Test that seed SQL can be executed without errors."""
        # Create an in-memory database with schema
        from app.db.schema import SCHEMA_SQL
        from app.db.seed import SEED_SQL
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)

        # Execute seed
        conn.executescript(SEED_SQL)
        conn.commit()

        # Verify data was inserted
        cursor = conn.cursor()

        # Check users_profile
        cursor.execute("SELECT COUNT(*) FROM users_profile")
        assert cursor.fetchone()[0] == 1

        # Check watchlist
        cursor.execute("SELECT COUNT(*) FROM watchlist")
        assert cursor.fetchone()[0] == 10

        conn.close()

    def test_seed_creates_default_user_profile(self):
        """Test that seed creates default user with $10,000 cash."""
        from app.db.schema import SCHEMA_SQL
        from app.db.seed import SEED_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
        cursor = conn.cursor()

        # Verify user profile
        cursor.execute("SELECT id, cash_balance FROM users_profile WHERE id = 'default'")
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "default"
        assert row[1] == 10000.0

        conn.close()

    def test_seed_creates_default_watchlist(self):
        """Test that seed creates watchlist with 10 default tickers."""
        from app.db.schema import SCHEMA_SQL
        from app.db.seed import SEED_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
        cursor = conn.cursor()

        # Expected tickers
        expected_tickers = {
            "AAPL",
            "GOOGL",
            "MSFT",
            "AMZN",
            "TSLA",
            "NVDA",
            "META",
            "JPM",
            "V",
            "NFLX",
        }

        # Get all tickers
        cursor.execute("SELECT ticker FROM watchlist WHERE user_id = 'default' ORDER BY ticker")
        tickers = {row[0] for row in cursor.fetchall()}

        assert tickers == expected_tickers

        conn.close()

    def test_seed_watchlist_has_correct_user_id(self):
        """Test that all watchlist entries have default user_id."""
        from app.db.schema import SCHEMA_SQL
        from app.db.seed import SEED_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM watchlist WHERE user_id != 'default' OR user_id IS NULL"
        )
        non_default_count = cursor.fetchone()[0]

        assert non_default_count == 0, "All watchlist entries should have user_id='default'"

        conn.close()

    def test_seed_is_idempotent(self):
        """Test that seed can be run multiple times without errors."""
        from app.db.schema import SCHEMA_SQL
        from app.db.seed import SEED_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)

        # Run seed twice
        conn.executescript(SEED_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
        cursor = conn.cursor()

        # Should still have exactly 1 user and 10 watchlist entries
        cursor.execute("SELECT COUNT(*) FROM users_profile")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM watchlist")
        assert cursor.fetchone()[0] == 10

        conn.close()

    def test_seed_watchlist_ids_are_uuid_format(self):
        """Test that all seeded watchlist IDs are in UUID format."""
        import re

        from app.db.schema import SCHEMA_SQL
        from app.db.seed import SEED_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM watchlist")
        ids = [row[0] for row in cursor.fetchall()]

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        for wid in ids:
            assert uuid_pattern.match(wid), f"Watchlist ID '{wid}' is not UUID format"

        conn.close()

    def test_seed_constants_are_defined(self):
        """Test that SEED_SQL constant is defined and non-empty."""
        from app.db.seed import SEED_SQL

        assert SEED_SQL is not None
        assert len(SEED_SQL) > 0
        assert "INSERT" in SEED_SQL
        assert "users_profile" in SEED_SQL
        assert "watchlist" in SEED_SQL

    def test_seed_watchlist_tickers_are_uppercase(self):
        """Test that all seeded tickers are uppercase."""
        from app.db.schema import SCHEMA_SQL
        from app.db.seed import SEED_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
        cursor = conn.cursor()

        cursor.execute("SELECT ticker FROM watchlist")
        tickers = [row[0] for row in cursor.fetchall()]

        for ticker in tickers:
            assert ticker.isupper(), f"Ticker {ticker} should be uppercase"

        conn.close()

    def test_seed_watchlist_has_unique_tickers(self):
        """Test that all seeded tickers are unique."""
        from app.db.schema import SCHEMA_SQL
        from app.db.seed import SEED_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(DISTINCT ticker) FROM watchlist")
        unique_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM watchlist")
        total_count = cursor.fetchone()[0]

        assert unique_count == total_count, "All tickers should be unique"

        conn.close()

    def test_seed_creates_timestamps(self):
        """Test that seed data includes timestamps."""
        from app.db.schema import SCHEMA_SQL
        from app.db.seed import SEED_SQL

        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
        cursor = conn.cursor()

        # Check user profile created_at
        cursor.execute("SELECT created_at FROM users_profile WHERE id = 'default'")
        created_at = cursor.fetchone()[0]
        assert created_at is not None
        assert len(created_at) > 0

        # Check watchlist added_at
        cursor.execute("SELECT COUNT(*) FROM watchlist WHERE added_at IS NULL")
        null_count = cursor.fetchone()[0]
        assert null_count == 0, "All watchlist entries should have added_at timestamp"

        conn.close()
