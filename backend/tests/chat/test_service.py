"""Tests for ChatService."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest

from app.chat.service import ChatService
from app.db import get_db
from app.market import PriceCache

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_db():
    """Provide a clean database state for each test."""
    db = get_db()
    db.init_db()

    yield db

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_messages WHERE user_id = 'test_user'")
        cursor.execute("DELETE FROM positions WHERE user_id = 'test_user'")
        cursor.execute("DELETE FROM trades WHERE user_id = 'test_user'")
        cursor.execute("DELETE FROM watchlist WHERE user_id = 'test_user'")
        conn.commit()


@pytest.fixture
def price_cache():
    """Price cache pre-populated with common test tickers."""
    cache = PriceCache()
    cache.update("AAPL", 190.00)
    cache.update("GOOGL", 175.00)
    cache.update("MSFT", 380.00)
    cache.update("TSLA", 220.00)
    cache.update("NVDA", 500.00)
    return cache


@pytest.fixture
def mock_chat_service(clean_db, price_cache, monkeypatch):
    """ChatService with LLM_MOCK=true — no real API calls, no side-effect trades."""
    monkeypatch.setenv("LLM_MOCK", "true")
    return ChatService(price_cache)


@pytest.fixture
def keyword_chat_service(clean_db, price_cache, monkeypatch):
    """ChatService wired to use the keyword-based mock response.

    _call_llm is patched at the instance level so no real HTTP requests are made,
    even if an OPENROUTER_API_KEY is present in the environment (e.g. via .env).
    """
    monkeypatch.setenv("LLM_MOCK", "false")
    service = ChatService(price_cache)

    async def _keyword_call_llm(message: str, context: dict) -> dict:
        return service._keyword_mock_response(message, context)

    # Bypass the real LiteLLM HTTP call
    monkeypatch.setattr(service, "_call_llm", _keyword_call_llm)
    return service


@pytest.fixture
def test_user_id():
    return "test_user"


def _seed_test_user(db, user_id: str, cash: float = 10000.0) -> None:
    """Insert a minimal user profile row for test_user."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, datetime('now'))",
            (user_id, cash),
        )
        cursor.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (cash, user_id),
        )
        conn.commit()


def _add_test_watchlist_ticker(db, user_id: str, ticker: str) -> None:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at)"
            " VALUES (?, ?, ?, datetime('now'))",
            (str(uuid.uuid4()), user_id, ticker),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# 1. Mock mode (LLM_MOCK=true) — deterministic, no trades
# ---------------------------------------------------------------------------


class TestMockMode:
    """When LLM_MOCK=true the service must return a valid ChatResponse with no actions."""

    async def test_mock_returns_valid_chat_response(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        response = await mock_chat_service.send_message("Hello AI!", user_id=test_user_id)

        assert response.message.role == "assistant"
        assert isinstance(response.message.content, str)
        assert len(response.message.content) > 0
        assert response.message.id != ""
        assert response.message.created_at.endswith("Z")

    async def test_mock_no_trades_executed(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        response = await mock_chat_service.send_message("Buy 10 shares of AAPL", user_id=test_user_id)

        # LLM_MOCK=true must not execute any trades
        assert response.executed_actions is None or len(response.executed_actions.trades) == 0

    async def test_mock_no_watchlist_changes(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        response = await mock_chat_service.send_message("Add TSLA to watchlist", user_id=test_user_id)

        assert response.executed_actions is None or len(response.executed_actions.watchlist_changes) == 0

    async def test_mock_acknowledges_message(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        msg = "What is my portfolio worth?"
        response = await mock_chat_service.send_message(msg, user_id=test_user_id)

        # Simple mock should echo/acknowledge the user message
        assert msg in response.message.content or "Mock mode" in response.message.content

    async def test_mock_deterministic_for_same_input(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        msg = "Tell me about my risk"
        r1 = await mock_chat_service.send_message(msg, user_id=test_user_id)
        r2 = await mock_chat_service.send_message(msg, user_id=test_user_id)

        assert r1.message.content == r2.message.content

    async def test_mock_messages_stored_in_db(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        await mock_chat_service.send_message("Hello!", user_id=test_user_id)

        with clean_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role FROM chat_messages WHERE user_id = ? ORDER BY created_at",
                (test_user_id,),
            )
            rows = cursor.fetchall()

        roles = [r["role"] for r in rows]
        assert "user" in roles
        assert "assistant" in roles


# ---------------------------------------------------------------------------
# 2. LLM response parsing — _parse_llm_response
# ---------------------------------------------------------------------------


class TestParseLlmResponse:
    """Unit tests for _parse_llm_response, isolated from DB and API."""

    @pytest.fixture
    def service(self, price_cache):
        return ChatService(price_cache)

    def test_parses_valid_full_json(self, service):
        content = json.dumps({
            "message": "I bought AAPL",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [{"ticker": "GOOGL", "action": "add"}],
        })
        result = service._parse_llm_response(content)

        assert result["message"] == "I bought AAPL"
        assert len(result["trades"]) == 1
        assert result["trades"][0]["ticker"] == "AAPL"
        assert len(result["watchlist_changes"]) == 1

    def test_parses_json_with_missing_trades_key(self, service):
        content = json.dumps({"message": "Just a reply"})
        result = service._parse_llm_response(content)

        assert result["message"] == "Just a reply"
        assert result["trades"] == []
        assert result["watchlist_changes"] == []

    def test_parses_json_empty_arrays(self, service):
        content = json.dumps({"message": "No action", "trades": [], "watchlist_changes": []})
        result = service._parse_llm_response(content)

        assert result["trades"] == []
        assert result["watchlist_changes"] == []

    def test_handles_malformed_json_extracts_message(self, service):
        malformed = '{"message": "Partial response here", "trades": [BROKEN'
        result = service._parse_llm_response(malformed)

        assert result["message"] == "Partial response here"
        assert result["trades"] == []
        assert result["watchlist_changes"] == []

    def test_handles_completely_invalid_json(self, service):
        result = service._parse_llm_response("not json at all ~~!!")

        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0
        assert result["trades"] == []
        assert result["watchlist_changes"] == []

    def test_handles_empty_string(self, service):
        result = service._parse_llm_response("")

        assert isinstance(result["message"], str)
        assert result["trades"] == []

    def test_handles_missing_message_key_in_valid_json(self, service):
        content = json.dumps({"trades": [], "watchlist_changes": []})
        result = service._parse_llm_response(content)

        # Should default to a fallback string
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_handles_escaped_quotes_in_message(self, service):
        content = '{"message": "It\\"s a reply", "trades": [], "watchlist_changes": []}'
        result = service._parse_llm_response(content)

        assert "reply" in result["message"]


# ---------------------------------------------------------------------------
# 3. Action execution — _execute_actions
# ---------------------------------------------------------------------------


class TestExecuteActions:
    """Tests for _execute_actions method with various LLM response shapes."""

    async def test_executes_valid_buy_trade(
        self, keyword_chat_service, clean_db, test_user_id, price_cache
    ):
        _seed_test_user(clean_db, test_user_id)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        llm_response = {
            "message": "Buying AAPL",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}],
            "watchlist_changes": [],
        }

        actions = await keyword_chat_service._execute_actions(llm_response, test_user_id)

        assert actions is not None
        assert len(actions.trades) == 1
        assert actions.trades[0].ticker == "AAPL"
        assert actions.trades[0].side == "buy"
        assert actions.trades[0].quantity == 5
        assert actions.trades[0].price == 190.00

    async def test_executes_multiple_trades(
        self, keyword_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id, cash=50000.0)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")
        _add_test_watchlist_ticker(clean_db, test_user_id, "GOOGL")

        llm_response = {
            "message": "Diversifying portfolio",
            "trades": [
                {"ticker": "AAPL", "side": "buy", "quantity": 5},
                {"ticker": "GOOGL", "side": "buy", "quantity": 3},
            ],
            "watchlist_changes": [],
        }

        actions = await keyword_chat_service._execute_actions(llm_response, test_user_id)

        assert actions is not None
        assert len(actions.trades) == 2

    async def test_insufficient_cash_trade_skipped_gracefully(
        self, keyword_chat_service, clean_db, test_user_id, price_cache
    ):
        _seed_test_user(clean_db, test_user_id, cash=100.0)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        llm_response = {
            "message": "I'll buy way too much",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1_000_000}],
            "watchlist_changes": [],
        }

        # Must not raise; failed trade is silently skipped
        actions = await keyword_chat_service._execute_actions(llm_response, test_user_id)

        assert actions is None or len(actions.trades) == 0

    async def test_insufficient_shares_sell_skipped_gracefully(
        self, keyword_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        llm_response = {
            "message": "Selling stock I don't own",
            "trades": [{"ticker": "AAPL", "side": "sell", "quantity": 50}],
            "watchlist_changes": [],
        }

        actions = await keyword_chat_service._execute_actions(llm_response, test_user_id)

        assert actions is None or len(actions.trades) == 0

    async def test_watchlist_add_action(
        self, keyword_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        # "NVDA" is not in test_user watchlist yet
        llm_response = {
            "message": "Adding NVDA",
            "trades": [],
            "watchlist_changes": [{"ticker": "NVDA", "action": "add"}],
        }

        actions = await keyword_chat_service._execute_actions(llm_response, test_user_id)

        assert actions is not None
        assert len(actions.watchlist_changes) == 1
        assert actions.watchlist_changes[0].ticker == "NVDA"
        assert actions.watchlist_changes[0].action == "added"

    async def test_watchlist_remove_action(
        self, keyword_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        _add_test_watchlist_ticker(clean_db, test_user_id, "TSLA")

        llm_response = {
            "message": "Removing TSLA",
            "trades": [],
            "watchlist_changes": [{"ticker": "TSLA", "action": "remove"}],
        }

        actions = await keyword_chat_service._execute_actions(llm_response, test_user_id)

        assert actions is not None
        assert actions.watchlist_changes[0].action == "removed"

        with clean_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ticker FROM watchlist WHERE user_id = ? AND ticker = 'TSLA'",
                (test_user_id,),
            )
            assert cursor.fetchone() is None

    async def test_duplicate_watchlist_add_skipped_gracefully(
        self, keyword_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        llm_response = {
            "message": "Add AAPL again",
            "trades": [],
            "watchlist_changes": [{"ticker": "AAPL", "action": "add"}],
        }

        actions = await keyword_chat_service._execute_actions(llm_response, test_user_id)

        assert actions is None or len(actions.watchlist_changes) == 0

    async def test_empty_llm_response_returns_none(
        self, keyword_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        llm_response = {"message": "Just chatting", "trades": [], "watchlist_changes": []}

        actions = await keyword_chat_service._execute_actions(llm_response, test_user_id)

        assert actions is None

    async def test_combined_trades_and_watchlist_changes(
        self, keyword_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id, cash=50000.0)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        llm_response = {
            "message": "Buy AAPL and watch NVDA",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 3}],
            "watchlist_changes": [{"ticker": "NVDA", "action": "add"}],
        }

        actions = await keyword_chat_service._execute_actions(llm_response, test_user_id)

        assert actions is not None
        assert len(actions.trades) == 1
        assert len(actions.watchlist_changes) == 1

    async def test_actions_stored_in_db(
        self, keyword_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        await keyword_chat_service.send_message("Buy AAPL", user_id=test_user_id)

        with clean_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT actions FROM chat_messages"
                " WHERE user_id = ? AND role = 'assistant'",
                (test_user_id,),
            )
            row = cursor.fetchone()

        assert row is not None
        actions_data = json.loads(row["actions"])
        assert "trades" in actions_data
        assert len(actions_data["trades"]) > 0


# ---------------------------------------------------------------------------
# 4. Trade validation within the full send_message flow
# ---------------------------------------------------------------------------


class TestTradeValidation:
    """Trade validation is enforced in the portfolio service during execute_actions."""

    async def test_buy_reduces_cash(
        self, keyword_chat_service, clean_db, test_user_id, price_cache
    ):
        _seed_test_user(clean_db, test_user_id, cash=10000.0)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        response = await keyword_chat_service.send_message("Buy AAPL", user_id=test_user_id)

        if response.executed_actions and response.executed_actions.trades:
            with clean_db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT cash_balance FROM users_profile WHERE id = ?",
                    (test_user_id,),
                )
                row = cursor.fetchone()
            assert row["cash_balance"] < 10000.0

    async def test_sell_after_buy_succeeds(
        self, keyword_chat_service, clean_db, test_user_id, price_cache
    ):
        _seed_test_user(clean_db, test_user_id, cash=10000.0)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        # Buy via keyword mock (10 shares)
        await keyword_chat_service.send_message("Buy AAPL", user_id=test_user_id)

        # Now sell some via keyword mock (5 shares)
        response = await keyword_chat_service.send_message("Sell AAPL", user_id=test_user_id)

        assert response.executed_actions is not None
        assert len(response.executed_actions.trades) > 0
        assert response.executed_actions.trades[0].side == "sell"

    async def test_sell_without_position_fails_gracefully(
        self, keyword_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        # No prior buy — should not raise, just return empty actions
        response = await keyword_chat_service.send_message("Sell AAPL", user_id=test_user_id)

        # The sell should fail validation silently
        assert response.message is not None  # Response still returned
        if response.executed_actions:
            assert len(response.executed_actions.trades) == 0

    async def test_buy_with_insufficient_cash_fails_gracefully(
        self, keyword_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id, cash=0.01)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        response = await keyword_chat_service.send_message("Buy AAPL", user_id=test_user_id)

        # Must not raise; trade simply not executed
        assert response.message is not None
        assert response.executed_actions is None or len(response.executed_actions.trades) == 0


# ---------------------------------------------------------------------------
# 5. Context building
# ---------------------------------------------------------------------------


class TestContextBuilding:

    async def test_build_context_returns_required_keys(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        context = await mock_chat_service._build_context(test_user_id)

        assert "portfolio" in context
        assert "watchlist" in context
        assert "history" in context

    async def test_build_context_empty_portfolio(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id, cash=10000.0)
        context = await mock_chat_service._build_context(test_user_id)

        assert context["portfolio"]["cash_balance"] == 10000.0
        assert len(context["portfolio"]["positions"]) == 0

    async def test_history_limited_to_20_messages(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)

        # Insert 25 messages directly
        with clean_db.get_connection() as conn:
            cursor = conn.cursor()
            for i in range(25):
                cursor.execute(
                    "INSERT INTO chat_messages (id, user_id, role, content, created_at)"
                    " VALUES (?, ?, 'user', ?, datetime('now'))",
                    (str(uuid.uuid4()), test_user_id, f"Message {i}"),
                )
            conn.commit()

        context = await mock_chat_service._build_context(test_user_id)
        assert len(context["history"]) <= 20

    def test_portfolio_context_string_includes_positions(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        context = {
            "portfolio": {
                "cash_balance": 5000.0,
                "total_value": 15000.0,
                "total_unrealized_pl": 500.0,
                "positions": [
                    {
                        "ticker": "AAPL",
                        "quantity": 10,
                        "avg_cost": 185.0,
                        "current_price": 190.0,
                        "market_value": 1900.0,
                        "cost_basis": 1850.0,
                        "unrealized_pl": 50.0,
                        "unrealized_pl_percent": 2.70,
                    }
                ],
            },
            "watchlist": [
                {"ticker": "AAPL", "price": 190.0, "change": 0.25, "change_percent": 0.13, "added_at": ""},
            ],
        }
        result = mock_chat_service._build_portfolio_context_string(context)

        assert "AAPL" in result
        assert "$5,000.00" in result
        assert "$15,000.00" in result

    def test_portfolio_context_string_no_positions(self, mock_chat_service):
        context = {
            "portfolio": {
                "cash_balance": 10000.0,
                "total_value": 10000.0,
                "total_unrealized_pl": 0.0,
                "positions": [],
            },
            "watchlist": [],
        }
        result = mock_chat_service._build_portfolio_context_string(context)
        assert "none" in result.lower() or "Positions: none" in result


# ---------------------------------------------------------------------------
# 6. General send_message flow
# ---------------------------------------------------------------------------


class TestSendMessageFlow:

    async def test_stores_user_and_assistant_messages(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        await mock_chat_service.send_message("Hello!", user_id=test_user_id)

        with clean_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM chat_messages"
                " WHERE user_id = ? ORDER BY created_at",
                (test_user_id,),
            )
            rows = cursor.fetchall()

        assert len(rows) == 2
        assert rows[0]["role"] == "user"
        assert rows[0]["content"] == "Hello!"
        assert rows[1]["role"] == "assistant"

    async def test_message_ids_are_unique(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        r1 = await mock_chat_service.send_message("Msg 1", user_id=test_user_id)
        r2 = await mock_chat_service.send_message("Msg 2", user_id=test_user_id)

        assert r1.message.id != r2.message.id

    async def test_timestamps_end_with_z(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        response = await mock_chat_service.send_message("Test", user_id=test_user_id)

        assert response.message.created_at.endswith("Z")
        # Must be parseable
        datetime.fromisoformat(response.message.created_at.replace("Z", ""))

    async def test_executed_actions_none_when_no_actions(
        self, mock_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        # Simple mock always returns no trades
        response = await mock_chat_service.send_message("Portfolio overview", user_id=test_user_id)

        assert response.executed_actions is None

    async def test_keyword_mock_buy_executes_trade(
        self, keyword_chat_service, clean_db, test_user_id, price_cache
    ):
        _seed_test_user(clean_db, test_user_id, cash=10000.0)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        response = await keyword_chat_service.send_message("Buy AAPL", user_id=test_user_id)

        assert response.executed_actions is not None
        assert len(response.executed_actions.trades) == 1
        assert response.executed_actions.trades[0].ticker == "AAPL"

    async def test_keyword_mock_sell_keywords(
        self, keyword_chat_service, clean_db, test_user_id, price_cache
    ):
        _seed_test_user(clean_db, test_user_id, cash=10000.0)
        _add_test_watchlist_ticker(clean_db, test_user_id, "AAPL")

        # Buy first so sell succeeds
        await keyword_chat_service.send_message("Buy AAPL", user_id=test_user_id)
        response = await keyword_chat_service.send_message("Sell AAPL", user_id=test_user_id)

        assert response.executed_actions is not None
        assert response.executed_actions.trades[0].side == "sell"

    async def test_keyword_mock_default_response_contains_portfolio_info(
        self, keyword_chat_service, clean_db, test_user_id
    ):
        _seed_test_user(clean_db, test_user_id)
        response = await keyword_chat_service.send_message(
            "What's the weather like?", user_id=test_user_id
        )

        assert "portfolio" in response.message.content.lower()
        assert response.executed_actions is None

    async def test_extract_ticker_from_various_inputs(self, mock_chat_service):
        assert mock_chat_service._extract_ticker("Buy AAPL now") == "AAPL"
        assert mock_chat_service._extract_ticker("How is GOOGL doing?") == "GOOGL"
        assert mock_chat_service._extract_ticker("no ticker here") is None
