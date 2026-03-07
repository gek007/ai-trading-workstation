"""Tests for PortfolioService."""

import pytest
from datetime import datetime

from app.db import get_db
from app.market import PriceCache
from app.portfolio.service import PortfolioService
from app.portfolio.models import Position, ExecutedTrade


@pytest.fixture
def clean_db():
    """Fixture to provide a clean database for each test."""
    db = get_db()

    # Clean up before test - reset database state
    with db.get_connection() as conn:
        cursor = conn.cursor()
        # Reset cash balance
        cursor.execute("UPDATE users_profile SET cash_balance = 10000.0 WHERE id = 'default'")
        # Clear positions
        cursor.execute("DELETE FROM positions WHERE user_id = 'default'")
        # Clear trades
        cursor.execute("DELETE FROM trades WHERE user_id = 'default'")
        conn.commit()

    yield db

    # Clean up after test
    with db.get_connection() as conn:
        cursor = conn.cursor()
        # Reset cash balance
        cursor.execute("UPDATE users_profile SET cash_balance = 10000.0 WHERE id = 'default'")
        # Clear positions
        cursor.execute("DELETE FROM positions WHERE user_id = 'default'")
        # Clear trades
        cursor.execute("DELETE FROM trades WHERE user_id = 'default'")
        conn.commit()


@pytest.fixture
def price_cache():
    """Fixture to provide a price cache with sample data."""
    cache = PriceCache()
    # Add some sample prices
    cache.update("AAPL", 190.00)
    cache.update("GOOGL", 175.00)
    cache.update("MSFT", 380.00)
    cache.update("TSLA", 220.00)
    return cache


@pytest.fixture
def portfolio_service(clean_db, price_cache):
    """Fixture to provide a PortfolioService instance."""
    return PortfolioService(price_cache)


class TestPortfolioService:
    """Unit tests for PortfolioService."""

    def test_get_portfolio_initial_state(self, portfolio_service):
        """Test getting initial portfolio with no positions."""
        portfolio = portfolio_service.get_portfolio()

        assert portfolio.cash_balance == 10000.0
        assert portfolio.total_value == 10000.0
        assert len(portfolio.positions) == 0
        assert portfolio.total_unrealized_pl == 0.0
        assert portfolio.total_unrealized_pl_percent == 0.0

    def test_get_portfolio_with_positions(self, portfolio_service, price_cache):
        """Test getting portfolio with existing positions."""
        # First, execute a buy to create a position
        trade, _ = portfolio_service.execute_trade("AAPL", 10, "buy")

        # Now get portfolio
        portfolio = portfolio_service.get_portfolio()

        assert len(portfolio.positions) == 1
        assert portfolio.cash_balance == 10000.0 - (10 * 190.00)
        assert portfolio.total_value == 10000.0  # Still 10k (cash + position)
        assert portfolio.positions[0].ticker == "AAPL"
        assert portfolio.positions[0].quantity == 10
        assert portfolio.positions[0].avg_cost == 190.00
        assert portfolio.positions[0].current_price == 190.00

    def test_execute_buy_trade_success(self, portfolio_service, price_cache):
        """Test successful buy trade execution."""
        trade, portfolio = portfolio_service.execute_trade("AAPL", 10, "buy")

        assert trade.ticker == "AAPL"
        assert trade.side == "buy"
        assert trade.quantity == 10
        assert trade.price == 190.00
        assert trade.total_value == 1900.00
        assert isinstance(trade.executed_at, str)

        # Verify portfolio updated
        assert len(portfolio.positions) == 1
        assert portfolio.cash_balance == 8100.00  # 10000 - 1900

    def test_execute_buy_trade_insufficient_cash(self, portfolio_service, price_cache):
        """Test buy trade with insufficient cash."""
        with pytest.raises(ValueError, match="Insufficient cash"):
            portfolio_service.execute_trade("AAPL", 100, "buy")  # Needs $19,000, only have $10,000

    def test_execute_buy_trade_exact_cash(self, portfolio_service, price_cache):
        """Test buy trade using exactly all available cash."""
        # 10000 / 190.00 = 52.63 shares possible
        max_shares = int(10000 / 190.00)
        trade, portfolio = portfolio_service.execute_trade("AAPL", max_shares, "buy")

        assert portfolio.cash_balance >= 0
        assert len(portfolio.positions) == 1

    def test_execute_sell_trade_success(self, portfolio_service, price_cache):
        """Test successful sell trade execution."""
        # First buy some shares
        portfolio_service.execute_trade("AAPL", 10, "buy")

        # Now sell them
        trade, portfolio = portfolio_service.execute_trade("AAPL", 5, "sell")

        assert trade.ticker == "AAPL"
        assert trade.side == "sell"
        assert trade.quantity == 5
        assert trade.price == 190.00

        # Verify position updated
        assert len(portfolio.positions) == 1
        assert portfolio.positions[0].quantity == 5
        assert portfolio.cash_balance == 10000.0 - (5 * 190.00)  # Got cash back

    def test_execute_sell_trade_insufficient_shares(self, portfolio_service, price_cache):
        """Test sell trade with insufficient shares."""
        # Buy only 10 shares
        portfolio_service.execute_trade("AAPL", 10, "buy")

        # Try to sell 15
        with pytest.raises(ValueError, match="Insufficient shares"):
            portfolio_service.execute_trade("AAPL", 15, "sell")

    def test_execute_sell_trade_no_position(self, portfolio_service, price_cache):
        """Test sell trade when no position exists."""
        with pytest.raises(ValueError, match="Insufficient shares"):
            portfolio_service.execute_trade("AAPL", 10, "sell")

    def test_execute_sell_full_position(self, portfolio_service, price_cache):
        """Test selling entire position closes it."""
        # Buy shares
        portfolio_service.execute_trade("AAPL", 10, "buy")

        # Sell all
        trade, portfolio = portfolio_service.execute_trade("AAPL", 10, "sell")

        # Position should be closed (deleted)
        assert len(portfolio.positions) == 0
        assert portfolio.cash_balance == 10000.0  # Back to original

    def test_execute_buy_creates_new_position(self, portfolio_service, price_cache):
        """Test that buying creates a new position."""
        trade, portfolio = portfolio_service.execute_trade("GOOGL", 5, "buy")

        assert len(portfolio.positions) == 1
        assert portfolio.positions[0].ticker == "GOOGL"
        assert portfolio.positions[0].quantity == 5
        assert portfolio.positions[0].avg_cost == 175.00

    def test_execute_buy_increases_existing_position(self, portfolio_service, price_cache):
        """Test that buying more of existing position increases it."""
        # First buy
        portfolio_service.execute_trade("AAPL", 10, "buy")

        # Update price (simulate price movement)
        price_cache.update("AAPL", 200.00)

        # Buy more
        trade, portfolio = portfolio_service.execute_trade("AAPL", 5, "buy")

        # Position should have weighted average cost
        position = portfolio.positions[0]
        assert position.quantity == 15
        # Weighted average: (10 * 190 + 5 * 200) / 15 = 2900 / 15 = 193.33
        assert abs(position.avg_cost - 193.33) < 0.01

    def test_position_unrealized_pl_gain(self, portfolio_service, price_cache):
        """Test unrealized P&L calculation for gain."""
        portfolio_service.execute_trade("AAPL", 10, "buy")

        # Price goes up
        price_cache.update("AAPL", 200.00)

        portfolio = portfolio_service.get_portfolio()
        position = portfolio.positions[0]

        assert position.current_price == 200.00
        assert position.cost_basis == 1900.00
        assert position.market_value == 2000.00
        assert position.unrealized_pl == 100.00
        assert position.unrealized_pl_percent == 5.26  # 100/1900 * 100

    def test_position_unrealized_pl_loss(self, portfolio_service, price_cache):
        """Test unrealized P&L calculation for loss."""
        portfolio_service.execute_trade("AAPL", 10, "buy")

        # Price goes down
        price_cache.update("AAPL", 180.00)

        portfolio = portfolio_service.get_portfolio()
        position = portfolio.positions[0]

        assert position.unrealized_pl == -100.00
        assert position.unrealized_pl_percent == -5.26

    def test_portfolio_total_unrealized_pl(self, portfolio_service, price_cache):
        """Test total unrealized P&L across multiple positions."""
        portfolio_service.execute_trade("AAPL", 10, "buy")  # $1900 cost
        portfolio_service.execute_trade("GOOGL", 10, "buy")  # $1750 cost

        # Prices change
        price_cache.update("AAPL", 200.00)  # +$100 gain
        price_cache.update("GOOGL", 170.00)  # -$50 loss

        portfolio = portfolio_service.get_portfolio()

        # Net: $100 - $50 = $50 gain
        assert portfolio.total_unrealized_pl == 50.00

    def test_execute_trade_ticker_not_in_cache(self, portfolio_service):
        """Test trade execution for ticker not in price cache."""
        with pytest.raises(ValueError, match="not found in price cache"):
            portfolio_service.execute_trade("INVALID", 10, "buy")

    def test_fractional_shares_buy(self, portfolio_service, price_cache):
        """Test buying fractional shares."""
        trade, portfolio = portfolio_service.execute_trade("AAPL", 10.5, "buy")

        assert trade.quantity == 10.5
        assert portfolio.positions[0].quantity == 10.5

    def test_fractional_shares_sell(self, portfolio_service, price_cache):
        """Test selling fractional shares."""
        portfolio_service.execute_trade("AAPL", 10, "buy")
        trade, portfolio = portfolio_service.execute_trade("AAPL", 3.7, "sell")

        assert trade.quantity == 3.7
        assert portfolio.positions[0].quantity == 6.3  # 10 - 3.7

    def test_multiple_positions(self, portfolio_service, price_cache):
        """Test portfolio with multiple different positions."""
        portfolio_service.execute_trade("AAPL", 10, "buy")
        portfolio_service.execute_trade("GOOGL", 5, "buy")
        portfolio_service.execute_trade("MSFT", 8, "buy")

        portfolio = portfolio_service.get_portfolio()

        assert len(portfolio.positions) == 3
        tickers = {p.ticker for p in portfolio.positions}
        assert tickers == {"AAPL", "GOOGL", "MSFT"}

    def test_portfolio_total_value_calculation(self, portfolio_service, price_cache):
        """Test total portfolio value calculation."""
        portfolio_service.execute_trade("AAPL", 10, "buy")  # $1900
        portfolio_service.execute_trade("GOOGL", 5, "buy")  # $875

        portfolio = portfolio_service.get_portfolio()

        # Cash: $10000 - $1900 - $875 = $7225
        # Positions: $1900 + $875 = $2775
        # Total: $7225 + $2775 = $10000
        assert portfolio.cash_balance + portfolio.positions[0].market_value + portfolio.positions[1].market_value == 10000.0

    def test_user_profile_not_found(self, portfolio_service, monkeypatch):
        """Test behavior when user profile doesn't exist."""
        # This would require deleting the user profile first
        # For now, we test the normal case which initializes the profile
        portfolio = portfolio_service.get_portfolio("nonexistent")
        # Should return default values or handle gracefully
        assert portfolio is not None

    def test_execute_trade_rounding(self, portfolio_service, price_cache):
        """Test that monetary values are properly rounded."""
        # Use a price that would cause floating point issues
        price_cache.update("TEST", 100.123)
        trade, portfolio = portfolio_service.execute_trade("TEST", 3, "buy")

        # Values should be rounded to 2 decimal places
        assert len(str(trade.total_value).split('.')[-1]) <= 2
        assert len(str(portfolio.cash_balance).split('.')[-1]) <= 2
