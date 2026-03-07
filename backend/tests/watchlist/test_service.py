"""Tests for WatchlistService."""

import pytest
import uuid
from datetime import datetime

from app.db import get_db
from app.market import PriceCache
from app.watchlist.service import WatchlistService
from app.watchlist.models import WatchlistItem


@pytest.fixture
def clean_db():
    """Fixture to provide a clean database for each test."""
    db = get_db()
    db.init_db()  # Initialize with seed data

    yield db

    # Clean up - reset database state
    # Note: we don't clear seed data, only test-specific additions
    with db.get_connection() as conn:
        cursor = conn.cursor()
        # Clear test-specific data (non-default users)
        cursor.execute("DELETE FROM watchlist WHERE user_id != 'default'")
        conn.commit()


@pytest.fixture
def price_cache():
    """Fixture to provide a price cache with sample data."""
    cache = PriceCache()
    # Add prices for default tickers
    cache.update("AAPL", 190.00)
    cache.update("GOOGL", 175.00)
    cache.update("MSFT", 380.00)
    cache.update("AMZN", 180.00)
    cache.update("TSLA", 220.00)
    cache.update("NVDA", 850.00)
    cache.update("META", 500.00)
    cache.update("JPM", 195.00)
    cache.update("V", 270.00)
    cache.update("NFLX", 600.00)
    return cache


@pytest.fixture
def watchlist_service(clean_db, price_cache):
    """Fixture to provide a WatchlistService instance."""
    return WatchlistService(price_cache, market_data_source=None)


class TestWatchlistService:
    """Unit tests for WatchlistService."""

    def test_get_watchlist_initial(self, watchlist_service, clean_db, price_cache):
        """Test getting initial empty watchlist."""
        # Clear the default seed data
        with clean_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            conn.commit()

        watchlist = watchlist_service.get_watchlist()

        assert len(watchlist.tickers) == 0

    def test_get_watchlist_with_seed_data(self, watchlist_service, price_cache):
        """Test getting watchlist with default seed data."""
        # Ensure seed data exists (it might have been cleared by other tests)
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM watchlist WHERE user_id = 'default'")
            count = cursor.fetchone()[0]
            if count == 0:
                # Re-seed the default watchlist
                from app.db.seed import SEED_SQL
                conn.executescript(SEED_SQL)
                conn.commit()

        watchlist = watchlist_service.get_watchlist()

        # Should have default tickers from seed data
        assert len(watchlist.tickers) > 0
        tickers = {t.ticker for t in watchlist.tickers}
        assert "AAPL" in tickers
        assert "GOOGL" in tickers

    def test_get_watchlist_with_prices(self, watchlist_service, price_cache):
        """Test that watchlist includes current prices from cache."""
        watchlist = watchlist_service.get_watchlist()

        # Find AAPL in the watchlist
        aapl_item = next((t for t in watchlist.tickers if t.ticker == "AAPL"), None)
        assert aapl_item is not None
        assert aapl_item.price == 190.00
        assert aapl_item.change == 0.0  # First update is flat

    def test_add_ticker_success(self, watchlist_service, price_cache):
        """Test successfully adding a ticker to watchlist."""
        # Clear seed data first
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            conn.commit()

        # Add price to cache for the ticker we're adding
        price_cache.update("NEW", 100.00)

        # Add a new ticker
        import asyncio
        asyncio.run(watchlist_service.add_ticker("NEW"))

        watchlist = watchlist_service.get_watchlist()

        assert len(watchlist.tickers) == 1
        assert watchlist.tickers[0].ticker == "NEW"

    def test_add_ticker_uppercase(self, watchlist_service, price_cache):
        """Test that ticker symbol is converted to uppercase."""
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            conn.commit()

        # Add price to cache
        price_cache.update("TEST", 150.00)

        import asyncio
        asyncio.run(watchlist_service.add_ticker("test"))  # lowercase

        watchlist = watchlist_service.get_watchlist()

        assert watchlist.tickers[0].ticker == "TEST"

    def test_add_ticker_strip_whitespace(self, watchlist_service, price_cache):
        """Test that whitespace is stripped from ticker."""
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            conn.commit()

        # Add price to cache
        price_cache.update("TEST", 150.00)

        import asyncio
        asyncio.run(watchlist_service.add_ticker("  TEST  "))

        watchlist = watchlist_service.get_watchlist()

        assert watchlist.tickers[0].ticker == "TEST"

    def test_add_duplicate_ticker_fails(self, watchlist_service, price_cache):
        """Test that adding duplicate ticker raises error."""
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            conn.commit()

        price_cache.update("TEST", 150.00)

        import asyncio
        asyncio.run(watchlist_service.add_ticker("TEST"))

        # Try to add again
        with pytest.raises(ValueError, match="already in your watchlist"):
            asyncio.run(watchlist_service.add_ticker("TEST"))

    def test_remove_ticker_success(self, watchlist_service, price_cache):
        """Test successfully removing a ticker from watchlist."""
        # First add a ticker
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'TEST', datetime('now'))",
                (str(uuid.uuid4()),)
            )
            conn.commit()

        price_cache.update("TEST", 150.00)

        import asyncio
        asyncio.run(watchlist_service.remove_ticker("TEST"))

        watchlist = watchlist_service.get_watchlist()

        assert len(watchlist.tickers) == 0

    def test_remove_ticker_uppercase(self, watchlist_service, price_cache):
        """Test that remove works with lowercase ticker."""
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'TEST', datetime('now'))",
                (str(uuid.uuid4()),)
            )
            conn.commit()

        price_cache.update("TEST", 150.00)

        import asyncio
        asyncio.run(watchlist_service.remove_ticker("test"))  # lowercase

        watchlist = watchlist_service.get_watchlist()

        assert len(watchlist.tickers) == 0

    def test_remove_nonexistent_ticker_fails(self, watchlist_service):
        """Test that removing non-existent ticker raises error."""
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            conn.commit()

        import asyncio
        with pytest.raises(ValueError, match="not in your watchlist"):
            asyncio.run(watchlist_service.remove_ticker("INVALID"))

    def test_get_all_tickers(self, watchlist_service):
        """Test getting all tickers as a list."""
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'AAPL', datetime('now'))",
                (str(uuid.uuid4()),)
            )
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'GOOGL', datetime('now'))",
                (str(uuid.uuid4()),)
            )
            conn.commit()

        tickers = watchlist_service.get_all_tickers()

        assert len(tickers) == 2
        assert "AAPL" in tickers
        assert "GOOGL" in tickers

    def test_watchlist_order_by_added_at(self, watchlist_service, price_cache):
        """Test that watchlist is ordered by addition time."""
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            # Add in specific order
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'AAPL', '2024-01-01 10:00:00')",
                (str(uuid.uuid4()),)
            )
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'GOOGL', '2024-01-01 09:00:00')",
                (str(uuid.uuid4()),)
            )
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'MSFT', '2024-01-01 11:00:00')",
                (str(uuid.uuid4()),)
            )
            conn.commit()

        # Add prices to cache so they show up in watchlist
        price_cache.update("AAPL", 190.00)
        price_cache.update("GOOGL", 175.00)
        price_cache.update("MSFT", 380.00)

        watchlist = watchlist_service.get_watchlist()

        # Should be ordered by added_at
        assert watchlist.tickers[0].ticker == "GOOGL"
        assert watchlist.tickers[1].ticker == "AAPL"
        assert watchlist.tickers[2].ticker == "MSFT"

    def test_watchlist_item_structure(self, watchlist_service, price_cache):
        """Test that watchlist items have correct structure."""
        watchlist = watchlist_service.get_watchlist()

        if len(watchlist.tickers) > 0:
            item = watchlist.tickers[0]
            assert isinstance(item.ticker, str)
            assert isinstance(item.price, float)
            assert isinstance(item.change, float)
            assert isinstance(item.change_percent, float)
            assert isinstance(item.added_at, str)

    def test_watchlist_price_updates(self, watchlist_service, price_cache):
        """Test that watchlist reflects price changes from cache."""
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'AAPL', datetime('now'))",
                (str(uuid.uuid4()),)
            )
            conn.commit()

        # Initial price
        price_cache.update("AAPL", 190.00)
        watchlist = watchlist_service.get_watchlist()
        initial_price = watchlist.tickers[0].price

        # Price goes up
        price_cache.update("AAPL", 200.00)
        watchlist = watchlist_service.get_watchlist()
        new_price = watchlist.tickers[0].price

        assert initial_price == 190.00
        assert new_price == 200.00
        assert watchlist.tickers[0].change == 10.00

    def test_watchlist_with_missing_price(self, watchlist_service, price_cache):
        """Test that tickers without prices are handled gracefully."""
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'NOTINCACHE', datetime('now'))",
                (str(uuid.uuid4()),)
            )
            conn.commit()

        watchlist = watchlist_service.get_watchlist()

        # Should not include tickers without prices
        not_in_cache = next((t for t in watchlist.tickers if t.ticker == "NOTINCACHE"), None)
        assert not_in_cache is None

    def test_multiple_users_independent(self, watchlist_service, price_cache):
        """Test that different users have independent watchlists."""
        # Add ticker for default user
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
            cursor.execute("DELETE FROM watchlist WHERE user_id = 'user2'")
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'AAPL', datetime('now'))",
                (str(uuid.uuid4()),)
            )
            # Add ticker for different user
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'user2', 'GOOGL', datetime('now'))",
                (str(uuid.uuid4()),)
            )
            conn.commit()

        # Add prices to cache
        price_cache.update("AAPL", 190.00)
        price_cache.update("GOOGL", 175.00)

        # Get watchlists
        default_watchlist = watchlist_service.get_watchlist("default")
        user2_watchlist = watchlist_service.get_watchlist("user2")

        assert len(default_watchlist.tickers) == 1
        assert default_watchlist.tickers[0].ticker == "AAPL"
        assert len(user2_watchlist.tickers) == 1
        assert user2_watchlist.tickers[0].ticker == "GOOGL"
