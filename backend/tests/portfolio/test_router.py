"""Tests for Portfolio API endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.db import get_db
from app.errors import AppError, app_error_handler
from app.market import PriceCache
from app.portfolio import create_portfolio_router


@pytest.fixture
def price_cache():
    """Provide a price cache with sample data."""
    cache = PriceCache()
    cache.update("AAPL", 190.00)
    cache.update("GOOGL", 175.00)
    cache.update("MSFT", 380.00)
    cache.update("TSLA", 220.00)
    return cache


@pytest.fixture
def clean_db():
    """Provide a clean database for each test."""
    db = get_db()
    db.init_db()

    def reset(conn):
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users_profile (id, cash_balance, created_at) "
            "VALUES ('default', 10000.0, datetime('now'))"
        )
        cursor.execute("DELETE FROM positions WHERE user_id = 'default'")
        cursor.execute("DELETE FROM trades WHERE user_id = 'default'")
        conn.commit()

    with db.get_connection() as conn:
        reset(conn)

    yield db

    with db.get_connection() as conn:
        reset(conn)


@pytest.fixture
def client(clean_db, price_cache):
    """Create a test client with a minimal app (no lifespan) for portfolio."""
    test_app = FastAPI()
    test_app.add_exception_handler(AppError, app_error_handler)
    router = create_portfolio_router(price_cache)
    test_app.include_router(router)
    return TestClient(test_app)


class TestPortfolioRouter:
    """Unit tests for Portfolio API endpoints."""

    def test_get_portfolio_initial_state(self, client):
        """Test GET /api/portfolio with no positions."""
        response = client.get("/api/portfolio")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["cash_balance"] == 10000.0
        assert data["total_value"] == 10000.0
        assert data["positions"] == []
        assert data["total_unrealized_pl"] == 0.0
        assert data["total_unrealized_pl_percent"] == 0.0

    def test_get_portfolio_with_positions(self, client):
        """Test GET /api/portfolio after executing a trade."""
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})

        response = client.get("/api/portfolio")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["positions"]) == 1
        assert data["cash_balance"] == 10000.0 - (10 * 190.00)
        assert abs(data["total_value"] - 10000.0) < 0.01

    def test_execute_buy_trade_success(self, client):
        """Test POST /api/portfolio/trade successful buy."""
        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "executed"
        trade = data["trade"]
        assert trade["ticker"] == "AAPL"
        assert trade["side"] == "buy"
        assert trade["quantity"] == 10
        assert trade["price"] == 190.00
        assert trade["total_value"] == 1900.00
        assert "id" in trade
        assert "executed_at" in trade
        assert data["portfolio"]["cash_balance"] == 8100.00
        assert len(data["portfolio"]["positions"]) == 1

    def test_execute_sell_trade_success(self, client):
        """Test POST /api/portfolio/trade successful sell."""
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})

        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 5, "side": "sell"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["trade"]["side"] == "sell"
        assert data["trade"]["quantity"] == 5
        assert len(data["portfolio"]["positions"]) == 1
        assert data["portfolio"]["positions"][0]["quantity"] == 5

    def test_execute_trade_ticker_normalization(self, client):
        """Test that lowercase ticker is normalized to uppercase."""
        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "aapl", "quantity": 10, "side": "buy"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["trade"]["ticker"] == "AAPL"

    def test_execute_trade_fractional_shares(self, client):
        """Test trading fractional shares."""
        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10.5, "side": "buy"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["trade"]["quantity"] == 10.5
        assert data["portfolio"]["positions"][0]["quantity"] == 10.5

    def test_execute_trade_invalid_ticker_format(self, client):
        """Test trade with ticker containing digits is rejected with 422."""
        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "aapl1", "quantity": 10, "side": "buy"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_execute_trade_invalid_quantity_zero(self, client):
        """Test trade with zero quantity is rejected with 422."""
        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 0, "side": "buy"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_execute_trade_quantity_precision_validation(self, client):
        """Test that quantity with more than 4 decimal places is rejected with 422."""
        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10.12345, "side": "buy"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_execute_trade_invalid_side(self, client):
        """Test trade with invalid side is rejected with 422."""
        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10, "side": "hold"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_execute_trade_ticker_not_found(self, client):
        """Test buy for ticker not in price cache returns 404 TICKER_NOT_FOUND."""
        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "XYZ", "quantity": 10, "side": "buy"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["error"]["code"] == "TICKER_NOT_FOUND"
        assert data["error"]["details"]["ticker"] == "XYZ"

    def test_execute_trade_insufficient_cash(self, client):
        """Test buy with insufficient cash returns 400 INSUFFICIENT_CASH."""
        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 100, "side": "buy"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["error"]["code"] == "INSUFFICIENT_CASH"
        assert data["error"]["details"]["ticker"] == "AAPL"
        assert "required" in data["error"]["details"]
        assert "available" in data["error"]["details"]

    def test_execute_trade_insufficient_shares(self, client):
        """Test sell more than owned returns 400 INSUFFICIENT_SHARES."""
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})

        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 15, "side": "sell"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["error"]["code"] == "INSUFFICIENT_SHARES"
        assert data["error"]["details"]["ticker"] == "AAPL"
        assert data["error"]["details"]["requested"] == 15
        assert data["error"]["details"]["owned"] == 10.0

    def test_sell_full_position_closes_it(self, client):
        """Test that selling the full position removes it."""
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})

        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10, "side": "sell"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["portfolio"]["positions"]) == 0
        assert data["portfolio"]["cash_balance"] == 10000.0

    def test_multiple_positions_portfolio_value(self, client):
        """Test portfolio total value with multiple positions."""
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
        client.post("/api/portfolio/trade", json={"ticker": "GOOGL", "quantity": 5, "side": "buy"})

        response = client.get("/api/portfolio")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["positions"]) == 2
        assert abs(data["total_value"] - 10000.0) < 0.01

    def test_portfolio_unrealized_pl_calculation(self, client, price_cache):
        """Test portfolio P&L updates with price movement."""
        client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})

        price_cache.update("AAPL", 200.00)

        response = client.get("/api/portfolio")
        assert response.status_code == status.HTTP_200_OK
        position = response.json()["positions"][0]

        assert position["unrealized_pl"] == 100.00
        assert abs(position["unrealized_pl_percent"] - 5.26) < 0.01

    def test_response_schema_compliance(self, client):
        """Test GET /api/portfolio response conforms to API contract schema."""
        response = client.get("/api/portfolio")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for field in ["cash_balance", "total_value", "positions", "total_unrealized_pl", "total_unrealized_pl_percent"]:
            assert field in data

    def test_trade_response_schema_compliance(self, client):
        """Test POST /api/portfolio/trade response conforms to API contract schema."""
        response = client.post(
            "/api/portfolio/trade",
            json={"ticker": "AAPL", "quantity": 10, "side": "buy"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "status" in data
        assert "trade" in data
        assert "portfolio" in data

        for field in ["id", "ticker", "side", "quantity", "price", "total_value", "executed_at"]:
            assert field in data["trade"]

        assert "cash_balance" in data["portfolio"]
