"""Integration tests for database operations."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

import pytest


class TestDatabaseIntegration:
    """Integration tests for database CRUD operations."""

    @pytest.fixture
    def db(self):
        """Fixture to provide initialized database."""
        from app.db import get_db

        db = get_db()
        db.init_db()

        # Clean up before test
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades WHERE user_id = 'default'")
            cursor.execute("DELETE FROM positions WHERE user_id = 'default'")
            cursor.execute("DELETE FROM chat_messages WHERE user_id = 'default'")
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            cursor.execute("DELETE FROM users_profile WHERE id != 'default'")
            cursor.execute("UPDATE users_profile SET cash_balance = 10000.0 WHERE id = 'default'")
            cursor.execute("DELETE FROM users_profile WHERE id = 'test-user'")
            conn.commit()

        yield db

        # Clean up after test
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades WHERE user_id = 'default'")
            cursor.execute("DELETE FROM positions WHERE user_id = 'default'")
            cursor.execute("DELETE FROM chat_messages WHERE user_id = 'default'")
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            cursor.execute("UPDATE users_profile SET cash_balance = 10000.0 WHERE id = 'default'")
            conn.commit()

    def test_user_profile_exists(self, db):
        """Test that default user profile exists."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cash_balance FROM users_profile WHERE id = 'default'")
            row = cursor.fetchone()

            assert row is not None
            assert row[0] == "default"
            assert row[1] == 10000.0

    def test_update_cash_balance(self, db):
        """Test updating user cash balance."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users_profile SET cash_balance = 5000.0 WHERE id = 'default'"
            )
            conn.commit()

            # Verify update
            cursor.execute("SELECT cash_balance FROM users_profile WHERE id = 'default'")
            balance = cursor.fetchone()[0]
            assert balance == 5000.0

    def test_insert_watchlist_entry(self, db):
        """Test inserting a new watchlist entry."""
        test_id = str(uuid.uuid4())

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (test_id, "default", "CASCADETEST", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

            # Verify insertion
            cursor.execute("SELECT ticker FROM watchlist WHERE id = ?", (test_id,))
            ticker = cursor.fetchone()[0]
            assert ticker == "CASCADETEST"

    def test_watchlist_unique_constraint(self, db):
        """Test that watchlist enforces unique(user_id, ticker)."""
        test_id1 = str(uuid.uuid4())
        test_id2 = str(uuid.uuid4())

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Insert first ticker
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (test_id1, "default", "DUPLICATE", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

            # Try to insert duplicate
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                    (test_id2, "default", "DUPLICATE", datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()

    def test_insert_position(self, db):
        """Test inserting a new position."""
        test_id = str(uuid.uuid4())

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (test_id, "default", "AAPL", 10.5, 190.0, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

            # Verify insertion
            cursor.execute("SELECT ticker, quantity, avg_cost FROM positions WHERE id = ?", (test_id,))
            row = cursor.fetchone()
            assert row[0] == "AAPL"
            assert row[1] == 10.5
            assert row[2] == 190.0

    def test_positions_unique_constraint(self, db):
        """Test that positions enforces unique(user_id, ticker)."""
        test_id1 = str(uuid.uuid4())
        test_id2 = str(uuid.uuid4())

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Insert first position
            cursor.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (test_id1, "default", "AAPL", 10, 190.0, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

            # Try to insert duplicate
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (test_id2, "default", "AAPL", 5, 200.0, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()

    def test_update_position(self, db):
        """Test updating an existing position."""
        test_id = str(uuid.uuid4())

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Insert initial position
            cursor.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (test_id, "default", "AAPL", 10, 190.0, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

            # Update position
            cursor.execute(
                "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? WHERE id = ?",
                (15, 195.0, datetime.now(timezone.utc).isoformat(), test_id),
            )
            conn.commit()

            # Verify update
            cursor.execute("SELECT quantity, avg_cost FROM positions WHERE id = ?", (test_id,))
            row = cursor.fetchone()
            assert row[0] == 15
            assert row[1] == 195.0

    def test_delete_position(self, db):
        """Test deleting a position."""
        test_id = str(uuid.uuid4())

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Insert position
            cursor.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (test_id, "default", "AAPL", 10, 190.0, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

            # Verify it exists
            cursor.execute("SELECT COUNT(*) FROM positions WHERE id = ?", (test_id,))
            assert cursor.fetchone()[0] == 1

            # Delete position
            cursor.execute("DELETE FROM positions WHERE id = ?", (test_id,))
            conn.commit()

            # Verify it's deleted
            cursor.execute("SELECT COUNT(*) FROM positions WHERE id = ?", (test_id,))
            assert cursor.fetchone()[0] == 0

    def test_insert_trade(self, db):
        """Test inserting a new trade."""
        test_id = str(uuid.uuid4())

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (test_id, "default", "AAPL", "buy", 10, 190.0, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

            # Verify insertion
            cursor.execute(
                "SELECT ticker, side, quantity, price FROM trades WHERE id = ?", (test_id,)
            )
            row = cursor.fetchone()
            assert row[0] == "AAPL"
            assert row[1] == "buy"
            assert row[2] == 10
            assert row[3] == 190.0

    def test_trade_side_check_constraint(self, db):
        """Test that trades enforces CHECK constraint on side."""
        test_id = str(uuid.uuid4())

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Try to insert invalid side
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (test_id, "default", "AAPL", "invalid", 10, 190.0, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()

    def test_get_trades_by_ticker(self, db):
        """Test retrieving trades by ticker."""
        # Insert multiple trades
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for i in range(3):
                test_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (test_id, "default", "AAPL", "buy", 10 * (i + 1), 190.0, datetime.now(timezone.utc).isoformat()),
                )
            conn.commit()

            # Query trades by ticker
            cursor.execute(
                "SELECT * FROM trades WHERE user_id = 'default' AND ticker = 'AAPL' ORDER BY quantity"
            )
            trades = cursor.fetchall()

            assert len(trades) == 3
            assert trades[0]["ticker"] == "AAPL"

    def test_insert_chat_message(self, db):
        """Test inserting a chat message."""
        test_id = str(uuid.uuid4())

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (test_id, "default", "user", "Hello AI", None, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

            # Verify insertion
            cursor.execute(
                "SELECT role, content, actions FROM chat_messages WHERE id = ?", (test_id,)
            )
            row = cursor.fetchone()
            assert row[0] == "user"
            assert row[1] == "Hello AI"
            assert row[2] is None

    def test_chat_message_with_actions(self, db):
        """Test inserting a chat message with JSON actions."""
        import json

        test_id = str(uuid.uuid4())
        actions = {
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [],
        }

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    test_id,
                    "default",
                    "assistant",
                    "I bought AAPL",
                    json.dumps(actions),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

            # Verify insertion
            cursor.execute("SELECT actions FROM chat_messages WHERE id = ?", (test_id,))
            actions_json = cursor.fetchone()[0]

            assert actions_json is not None
            parsed_actions = json.loads(actions_json)
            assert parsed_actions["trades"][0]["ticker"] == "AAPL"

    def test_chat_message_role_check_constraint(self, db):
        """Test that chat_messages enforces CHECK constraint on role."""
        test_id = str(uuid.uuid4())

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Try to insert invalid role
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (test_id, "default", "system", "test", None, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()

    def test_get_recent_chat_messages(self, db):
        """Test retrieving recent chat messages."""
        # Insert multiple messages
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for i in range(5):
                test_id = str(uuid.uuid4())
                role = "user" if i % 2 == 0 else "assistant"
                cursor.execute(
                    "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (test_id, "default", role, f"Message {i}", None, datetime.now(timezone.utc).isoformat()),
                )
            conn.commit()

            # Query recent messages
            cursor.execute(
                "SELECT * FROM chat_messages WHERE user_id = 'default' ORDER BY created_at DESC LIMIT 3"
            )
            messages = cursor.fetchall()

            assert len(messages) == 3

    def test_cascade_delete_from_users_profile(self, db):
        """Test that deleting a user cascades to related tables."""
        # Create a test user (use unique ID to avoid conflicts)
        import random
        test_user_id = f"test-cascade-user-{random.randint(1000, 9999)}"

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Clean up any existing test data first
            cursor.execute("DELETE FROM chat_messages WHERE user_id = ?", (test_user_id,))
            cursor.execute("DELETE FROM trades WHERE user_id = ?", (test_user_id,))
            cursor.execute("DELETE FROM positions WHERE user_id = ?", (test_user_id,))
            cursor.execute("DELETE FROM watchlist WHERE user_id = ?", (test_user_id,))
            cursor.execute("DELETE FROM users_profile WHERE id = ?", (test_user_id,))
            conn.commit()

            # Insert test user
            cursor.execute(
                "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
                (test_user_id, 5000.0, datetime.now(timezone.utc).isoformat()),
            )

            # Add related data
            watchlist_id = str(uuid.uuid4())
            position_id = str(uuid.uuid4())
            trade_id = str(uuid.uuid4())
            chat_id = str(uuid.uuid4())

            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (watchlist_id, test_user_id, "CASCADETEST", datetime.now(timezone.utc).isoformat()),
            )
            cursor.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (position_id, test_user_id, "CASCADETEST", 10, 100.0, datetime.now(timezone.utc).isoformat()),
            )
            cursor.execute(
                "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (trade_id, test_user_id, "CASCADETEST", "buy", 10, 100.0, datetime.now(timezone.utc).isoformat()),
            )
            cursor.execute(
                "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, test_user_id, "user", "test", None, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

            # Verify data exists
            cursor.execute("SELECT COUNT(*) FROM watchlist WHERE user_id = ?", (test_user_id,))
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT COUNT(*) FROM positions WHERE user_id = ?", (test_user_id,))
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT COUNT(*) FROM trades WHERE user_id = ?", (test_user_id,))
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (test_user_id,))
            assert cursor.fetchone()[0] == 1

            # Delete user
            cursor.execute("DELETE FROM users_profile WHERE id = ?", (test_user_id,))
            conn.commit()

            # Verify cascade delete worked
            cursor.execute("SELECT COUNT(*) FROM watchlist WHERE user_id = ?", (test_user_id,))
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM positions WHERE user_id = ?", (test_user_id,))
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM trades WHERE user_id = ?", (test_user_id,))
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (test_user_id,))
            assert cursor.fetchone()[0] == 0

    def test_transaction_rollback_on_error(self, db):
        """Test that transactions roll back on errors."""
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Get initial cash balance
            cursor.execute("SELECT cash_balance FROM users_profile WHERE id = 'default'")
            initial_balance = cursor.fetchone()[0]

            # Start a transaction
            try:
                cursor.execute(
                    "UPDATE users_profile SET cash_balance = cash_balance - 1000 WHERE id = 'default'"
                )
                # Simulate an error
                raise ValueError("Simulated error")
            except ValueError:
                conn.rollback()

            # Verify balance was restored
            cursor.execute("SELECT cash_balance FROM users_profile WHERE id = 'default'")
            final_balance = cursor.fetchone()[0]
            assert final_balance == initial_balance

    def test_transaction_commit_on_success(self, db):
        """Test that transactions commit on success."""
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Update cash balance
            cursor.execute(
                "UPDATE users_profile SET cash_balance = 9000.0 WHERE id = 'default'"
            )
            conn.commit()

            # Verify update persisted
            cursor.execute("SELECT cash_balance FROM users_profile WHERE id = 'default'")
            balance = cursor.fetchone()[0]
            assert balance == 9000.0

    def test_index_performance_on_user_id(self, db):
        """Test that indexes exist on user_id columns for all key tables."""
        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            )
            indexes = [row[0] for row in cursor.fetchall()]

            assert any("watchlist" in idx.lower() for idx in indexes), (
                "Missing index on watchlist(user_id)"
            )
            assert any("positions" in idx.lower() for idx in indexes), (
                "Missing index on positions(user_id)"
            )
            assert any("trades" in idx.lower() for idx in indexes), (
                "Missing index on trades(user_id)"
            )
            # Chat messages use a compound (user_id, created_at) index
            assert any("chat" in idx.lower() for idx in indexes), (
                "Missing index on chat_messages"
            )
