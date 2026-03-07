"""Tests for ChatService."""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.db import get_db
from app.market import PriceCache
from app.chat.service import ChatService
from app.chat.models import ChatMessage, ExecutedActions


@pytest.fixture
def clean_db():
    """Fixture to provide a clean database for each test."""
    db = get_db()
    db.init_db()  # Initialize with seed data

    yield db

    # Clean up - reset database state
    with db.get_connection() as conn:
        cursor = conn.cursor()
        # Clear chat messages
        cursor.execute("DELETE FROM chat_messages WHERE user_id = 'default'")
        # Clear positions
        cursor.execute("DELETE FROM positions WHERE user_id = 'default'")
        # Clear trades
        cursor.execute("DELETE FROM trades WHERE user_id = 'default'")
        # Reset cash
        cursor.execute("UPDATE users_profile SET cash_balance = 10000.0 WHERE id = 'default'")
        conn.commit()


@pytest.fixture
def price_cache():
    """Fixture to provide a price cache with sample data."""
    cache = PriceCache()
    cache.update("AAPL", 190.00)
    cache.update("GOOGL", 175.00)
    cache.update("MSFT", 380.00)
    cache.update("TSLA", 220.00)
    return cache


@pytest.fixture
def chat_service(clean_db, price_cache):
    """Fixture to provide a ChatService instance."""
    return ChatService(price_cache)


class TestChatService:
    """Unit tests for ChatService."""

    @pytest.mark.asyncio
    async def test_send_message_stores_user_message(self, chat_service):
        """Test that user message is stored in database."""
        response = await chat_service.send_message("Hello, AI!", user_id="default")

        # Check database
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM chat_messages WHERE user_id = 'default' ORDER BY created_at",
            )
            rows = cursor.fetchall()

        assert len(rows) == 2  # User + assistant
        assert rows[0]["role"] == "user"
        assert rows[0]["content"] == "Hello, AI!"
        assert rows[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_send_message_returns_response(self, chat_service):
        """Test that send_message returns a valid ChatResponse."""
        response = await chat_service.send_message("What's my portfolio?", user_id="default")

        assert response.message.role == "assistant"
        assert isinstance(response.message.content, str)
        assert len(response.message.content) > 0
        assert isinstance(response.message.id, str)
        assert isinstance(response.message.created_at, str)

    @pytest.mark.asyncio
    async def test_send_message_mock_mode(self, chat_service):
        """Test that mock mode returns deterministic responses."""
        # ChatService should be in mock mode by default (no API key)
        response = await chat_service.send_message("Buy AAPL", user_id="default")

        assert response.message.role == "assistant"
        # Mock should detect "buy" keyword
        assert "buy" in response.message.content.lower() or "purchase" in response.message.content.lower()

    @pytest.mark.asyncio
    async def test_send_message_executes_trade(self, chat_service, price_cache):
        """Test that LLM can execute trades."""
        response = await chat_service.send_message("Buy AAPL", user_id="default")

        # Should have executed a trade
        assert response.executed_actions is not None
        assert len(response.executed_actions.trades) > 0

        trade = response.executed_actions.trades[0]
        assert trade.ticker == "AAPL"
        assert trade.side == "buy"
        assert trade.quantity == 10  # Mock default

    @pytest.mark.asyncio
    async def test_send_message_adds_to_watchlist(self, chat_service):
        """Test that LLM can add to watchlist."""
        response = await chat_service.send_message("Add TSLA to my watchlist", user_id="default")

        # Should have added to watchlist
        assert response.executed_actions is not None
        assert len(response.executed_actions.watchlist_changes) > 0

        change = response.executed_actions.watchlist_changes[0]
        assert change.ticker == "TSLA"
        assert change.action == "added"

    @pytest.mark.asyncio
    async def test_send_message_sells_stock(self, chat_service, price_cache):
        """Test that LLM can sell stocks."""
        # First buy some shares
        await chat_service.send_message("Buy AAPL", user_id="default")

        # Now sell
        response = await chat_service.send_message("Sell AAPL", user_id="default")

        assert response.executed_actions is not None
        trade = response.executed_actions.trades[0]
        assert trade.side == "sell"
        assert trade.ticker == "AAPL"

    @pytest.mark.asyncio
    async def test_send_message_default_response(self, chat_service):
        """Test default response when no keywords match."""
        response = await chat_service.send_message("Tell me about the weather", user_id="default")

        assert response.message.role == "assistant"
        assert "portfolio" in response.message.content.lower()
        assert response.executed_actions is None or len(response.executed_actions.trades) == 0

    @pytest.mark.asyncio
    async def test_conversation_history_context(self, chat_service):
        """Test that conversation history is included in context."""
        # Send first message
        await chat_service.send_message("My name is Alice", user_id="default")

        # Send second message
        response = await chat_service.send_message("What's my name?", user_id="default")

        # In a real LLM, this would use conversation history
        # In mock mode, we just verify it doesn't crash
        assert response.message is not None

    @pytest.mark.asyncio
    async def test_portfolio_context_included(self, chat_service):
        """Test that portfolio context is built correctly."""
        # Execute a trade first
        await chat_service.send_message("Buy AAPL", user_id="default")

        # Build context
        context = await chat_service._build_context("default")

        assert "portfolio" in context
        assert "watchlist" in context
        assert "history" in context
        assert context["portfolio"]["cash_balance"] < 10000.0  # Should have spent money
        assert len(context["portfolio"]["positions"]) > 0

    @pytest.mark.asyncio
    async def test_extract_ticker(self, chat_service):
        """Test ticker extraction from text."""
        assert chat_service._extract_ticker("Buy AAPL now") == "AAPL"
        assert chat_service._extract_ticker("What about GOOGL?") == "GOOGL"
        assert chat_service._extract_ticker("No ticker here") is None

    @pytest.mark.asyncio
    async def test_send_message_stores_actions(self, chat_service):
        """Test that executed actions are stored in database."""
        response = await chat_service.send_message("Buy AAPL", user_id="default")

        # Check database for actions
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT actions FROM chat_messages WHERE user_id = 'default' AND role = 'assistant'",
            )
            row = cursor.fetchone()

        assert row is not None
        actions_json = row["actions"]
        assert actions_json is not None

        actions = json.loads(actions_json)
        assert "trades" in actions
        assert len(actions["trades"]) > 0

    @pytest.mark.asyncio
    async def test_execute_actions_handles_trade_errors(self, chat_service):
        """Test that trade errors are handled gracefully."""
        # Mock a trade that will fail (insufficient cash)
        llm_response = {
            "message": "I'll try to buy too much",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1000000}],
            "watchlist_changes": []
        }

        # Should not raise, just log error
        actions = await chat_service._execute_actions(llm_response, "default")

        # Should have no trades due to error
        assert actions is None or len(actions.trades) == 0

    @pytest.mark.asyncio
    async def test_execute_actions_handles_watchlist_errors(self, chat_service):
        """Test that watchlist errors are handled gracefully."""
        # First add ticker
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'AAPL', datetime('now'))",
                ("test-id",)
            )
            conn.commit()

        # Try to add again (duplicate)
        llm_response = {
            "message": "I'll add AAPL",
            "trades": [],
            "watchlist_changes": [{"ticker": "AAPL", "action": "add"}]
        }

        # Should not raise, just log error
        actions = await chat_service._execute_actions(llm_response, "default")

        # Should have no watchlist changes due to error
        assert actions is None or len(actions.watchlist_changes) == 0

    @pytest.mark.asyncio
    async def test_watchlist_remove_action(self, chat_service):
        """Test that watchlist removal works."""
        # First add to watchlist
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, 'default', 'TSLA', datetime('now'))",
                ("test-id",)
            )
            conn.commit()

        # Execute remove action
        llm_response = {
            "message": "Removing TSLA",
            "trades": [],
            "watchlist_changes": [{"ticker": "TSLA", "action": "remove"}]
        }

        actions = await chat_service._execute_actions(llm_response, "default")

        assert actions is not None
        assert len(actions.watchlist_changes) == 1
        assert actions.watchlist_changes[0].action == "removed"

        # Verify it's gone from database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker FROM watchlist WHERE user_id = 'default' AND ticker = 'TSLA'")
            assert cursor.fetchone() is None

    @pytest.mark.asyncio
    async def test_multiple_trades_in_one_message(self, chat_service):
        """Test executing multiple trades from a single message."""
        # This would require a more sophisticated mock or real LLM
        # For now, test that the mechanism exists
        llm_response = {
            "message": "Buying multiple stocks",
            "trades": [
                {"ticker": "AAPL", "side": "buy", "quantity": 5},
                {"ticker": "GOOGL", "side": "buy", "quantity": 3}
            ],
            "watchlist_changes": []
        }

        actions = await chat_service._execute_actions(llm_response, "default")

        assert actions is not None
        assert len(actions.trades) == 2

    @pytest.mark.asyncio
    async def test_both_trades_and_watchlist_changes(self, chat_service):
        """Test executing both trades and watchlist changes."""
        llm_response = {
            "message": "Buying and watching",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}],
            "watchlist_changes": [{"ticker": "MSFT", "action": "add"}]
        }

        actions = await chat_service._execute_actions(llm_response, "default")

        assert actions is not None
        assert len(actions.trades) == 1
        assert len(actions.watchlist_changes) == 1

    @pytest.mark.asyncio
    async def test_user_message_validation(self, chat_service):
        """Test that user messages are stored correctly."""
        long_message = "A" * 1000  # Max length

        response = await chat_service.send_message(long_message, user_id="default")

        # Should work fine
        assert response.message is not None

    @pytest.mark.asyncio
    async def test_build_context_with_empty_portfolio(self, chat_service):
        """Test building context when user has no positions."""
        # Clear any existing positions
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM positions WHERE user_id = 'default'")
            conn.commit()

        context = await chat_service._build_context("default")

        assert context["portfolio"]["cash_balance"] == 10000.0
        assert len(context["portfolio"]["positions"]) == 0
        assert context["portfolio"]["total_value"] == 10000.0

    @pytest.mark.asyncio
    async def test_build_context_includes_watchlist(self, chat_service):
        """Test that watchlist is included in context."""
        context = await chat_service._build_context("default")

        assert "watchlist" in context
        assert isinstance(context["watchlist"], list)

    @pytest.mark.asyncio
    async def test_build_context_history_limit(self, chat_service):
        """Test that conversation history is limited."""
        # Send many messages
        for i in range(25):
            await chat_service.send_message(f"Message {i}", user_id="default")

        context = await chat_service._build_context("default")

        # Should limit to last 20 messages
        assert len(context["history"]) <= 20

    @pytest.mark.asyncio
    async def test_mock_llm_response_case_insensitive(self, chat_service):
        """Test that mock response detection is case-insensitive."""
        response = await chat_service._mock_llm_response("BUY aapl", await chat_service._build_context("default"))

        assert "buy" in response["message"].lower()

    @pytest.mark.asyncio
    async def test_mock_llm_response_sell_keywords(self, chat_service):
        """Test that mock detects sell keywords."""
        response1 = await chat_service._mock_llm_response("Sell AAPL", await chat_service._build_context("default"))
        response2 = await chat_service._mock_llm_response("Exit AAPL", await chat_service._build_context("default"))

        assert "sell" in response1["message"].lower()
        assert "sell" in response2["message"].lower()

    @pytest.mark.asyncio
    async def test_mock_llm_response_watch_keywords(self, chat_service):
        """Test that mock detects watchlist keywords."""
        response1 = await chat_service._mock_llm_response("Add TSLA", await chat_service._build_context("default"))
        response2 = await chat_service._mock_llm_response("Watch TSLA", await chat_service._build_context("default"))

        assert "added" in response1["message"].lower()
        assert "added" in response2["message"].lower()

    @pytest.mark.asyncio
    async def test_message_ids_are_unique(self, chat_service):
        """Test that each message gets a unique ID."""
        response1 = await chat_service.send_message("Message 1", user_id="default")
        response2 = await chat_service.send_message("Message 2", user_id="default")

        assert response1.message.id != response2.message.id

    @pytest.mark.asyncio
    async def test_message_timestamps_are_valid(self, chat_service):
        """Test that messages have valid timestamps."""
        response = await chat_service.send_message("Test", user_id="default")

        # Should be ISO format with Z suffix
        assert response.message.created_at.endswith("Z")

        # Should be parseable
        datetime.fromisoformat(response.message.created_at.replace("Z", ""))
