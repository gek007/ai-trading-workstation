"""Tests for Watchlist API endpoints."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.errors import AppError, app_error_handler
from app.market import PriceCache
from app.watchlist import create_watchlist_router


@pytest.fixture
def price_cache():
    """Provide a price cache with sample data."""
    cache = PriceCache()
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
def clean_db():
    """Provide a clean database state for each test."""
    db = get_db()
    db.init_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
        conn.commit()

    yield db

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE user_id = 'default'")
        conn.commit()


@pytest.fixture
def client(price_cache):
    """Create a test client with a minimal app (no lifespan) for watchlist."""
    test_app = FastAPI()
    test_app.add_exception_handler(AppError, app_error_handler)
    router = create_watchlist_router(price_cache, market_data_source=None)
    test_app.include_router(router)
    return TestClient(test_app)


class TestWatchlistRouter:
    """Integration tests for watchlist API endpoints."""

    def test_get_watchlist_success(self, client, clean_db):
        """Test successfully getting the watchlist."""
        response = client.get("/api/watchlist")

        assert response.status_code == 200
        data = response.json()
        assert "tickers" in data
        assert isinstance(data["tickers"], list)

    def test_get_empty_watchlist(self, client, clean_db):
        """Test getting an empty watchlist."""
        response = client.get("/api/watchlist")

        assert response.status_code == 200
        data = response.json()
        assert data["tickers"] == []

    def test_get_watchlist_with_prices(self, client, clean_db, price_cache):
        """Test that watchlist includes current prices from cache."""
        with clean_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'AAPL', datetime('now'))",
                (str(uuid.uuid4()),),
            )
            conn.commit()

        response = client.get("/api/watchlist")

        assert response.status_code == 200
        data = response.json()
        first_ticker = data["tickers"][0]
        assert first_ticker["ticker"] == "AAPL"
        assert first_ticker["price"] == 190.00
        assert "change" in first_ticker
        assert "change_percent" in first_ticker
        assert "added_at" in first_ticker

    def test_add_ticker_success(self, client, clean_db, price_cache):
        """Test successfully adding a ticker to watchlist."""
        price_cache.update("PYPL", 280.00)
        response = client.post("/api/watchlist", json={"ticker": "PYPL"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "added"
        assert data["ticker"] == "PYPL"
        assert "watchlist" in data
        tickers = [t["ticker"] for t in data["watchlist"]["tickers"]]
        assert "PYPL" in tickers

    def test_add_ticker_lowercase_normalized(self, client, clean_db, price_cache):
        """Test that lowercase ticker is normalized to uppercase."""
        price_cache.update("TEST", 150.00)
        response = client.post("/api/watchlist", json={"ticker": "test"})

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TEST"

    def test_add_duplicate_ticker_returns_409(self, client, clean_db, price_cache):
        """Test that adding a duplicate ticker returns 409 with WATCHLIST_EXISTS error."""
        price_cache.update("TEST", 150.00)

        client.post("/api/watchlist", json={"ticker": "TEST"})
        response = client.post("/api/watchlist", json={"ticker": "TEST"})

        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "WATCHLIST_EXISTS"
        assert "already in your watchlist" in data["error"]["message"]
        assert data["error"]["details"]["ticker"] == "TEST"

    def test_add_ticker_with_numbers_rejected(self, client, clean_db):
        """Test that ticker with digits is rejected with 422."""
        response = client.post("/api/watchlist", json={"ticker": "AAPL1"})
        assert response.status_code == 422

    def test_add_ticker_too_long_rejected(self, client, clean_db):
        """Test that ticker longer than 5 chars is rejected with 422."""
        response = client.post("/api/watchlist", json={"ticker": "TOOLONG"})
        assert response.status_code == 422

    def test_add_ticker_empty_rejected(self, client, clean_db):
        """Test that empty ticker is rejected with 422."""
        response = client.post("/api/watchlist", json={"ticker": ""})
        assert response.status_code == 422

    def test_add_ticker_special_chars_rejected(self, client, clean_db):
        """Test that ticker with special characters is rejected with 422."""
        response = client.post("/api/watchlist", json={"ticker": "AAPL!"})
        assert response.status_code == 422

    def test_remove_ticker_success(self, client, clean_db, price_cache):
        """Test successfully removing a ticker from watchlist."""
        with clean_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'TEST', datetime('now'))",
                (str(uuid.uuid4()),),
            )
            conn.commit()

        price_cache.update("TEST", 150.00)
        response = client.delete("/api/watchlist/TEST")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "removed"
        assert data["ticker"] == "TEST"
        assert "watchlist" in data

    def test_remove_ticker_case_insensitive(self, client, clean_db, price_cache):
        """Test that remove works with lowercase ticker path."""
        with clean_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'TEST', datetime('now'))",
                (str(uuid.uuid4()),),
            )
            conn.commit()

        price_cache.update("TEST", 150.00)
        response = client.delete("/api/watchlist/test")

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TEST"

    def test_remove_nonexistent_ticker_returns_404(self, client, clean_db):
        """Test that removing a non-existent ticker returns 404 with WATCHLIST_NOT_FOUND."""
        response = client.delete("/api/watchlist/INVALID")

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "WATCHLIST_NOT_FOUND"
        assert "not in your watchlist" in data["error"]["message"]
        assert data["error"]["details"]["ticker"] == "INVALID"

    def test_error_response_format(self, client, clean_db):
        """Test that error responses follow the contract format."""
        response = client.delete("/api/watchlist/NONEXIST")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert isinstance(data["error"], dict)
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "details" in data["error"]
        assert isinstance(data["error"]["code"], str)
        assert isinstance(data["error"]["message"], str)

    def test_watchlist_ordering_by_added_at(self, client, clean_db, price_cache):
        """Test that watchlist is sorted by added_at (oldest first)."""
        with clean_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'AAPL', '2024-01-01 10:00:00')",
                (str(uuid.uuid4()),),
            )
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'GOOGL', '2024-01-01 09:00:00')",
                (str(uuid.uuid4()),),
            )
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'MSFT', '2024-01-01 11:00:00')",
                (str(uuid.uuid4()),),
            )
            conn.commit()

        response = client.get("/api/watchlist")
        assert response.status_code == 200
        tickers = [t["ticker"] for t in response.json()["tickers"]]
        assert tickers == ["GOOGL", "AAPL", "MSFT"]

    def test_watchlist_price_updates(self, client, clean_db, price_cache):
        """Test that watchlist reflects price changes from the cache."""
        with clean_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'AAPL', datetime('now'))",
                (str(uuid.uuid4()),),
            )
            conn.commit()

        price_cache.update("AAPL", 190.00)
        data1 = client.get("/api/watchlist").json()
        assert data1["tickers"][0]["price"] == 190.00

        price_cache.update("AAPL", 200.00)
        data2 = client.get("/api/watchlist").json()
        assert data2["tickers"][0]["price"] == 200.00
        assert data2["tickers"][0]["change"] == 10.00
