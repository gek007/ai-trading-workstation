"""Chat service - LLM integration and chat management."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

from app.db import get_db
from app.market import PriceCache
from app.chat.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ExecutedActions,
    ExecutedTrade,
    WatchlistChange,
)


class ChatService:
    """Service for AI-powered chat and trade execution."""

    def __init__(self, price_cache: PriceCache):
        self._cache = price_cache
        self._mock_mode = os.environ.get("LLM_MOCK", "false").strip().lower() == "true"

    async def send_message(self, message: str, user_id: str = "default") -> ChatResponse:
        """Process a user message through the LLM and execute any actions.

        The LLM may auto-execute trades or modify the watchlist based on the conversation.
        """
        # 1. Store user message in database
        user_message_id = str(uuid.uuid4())
        user_created_at = datetime.utcnow().isoformat() + "Z"

        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_messages (id, user_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_message_id, user_id, "user", message, user_created_at),
            )
            conn.commit()

        # 2. Get conversation context (portfolio + history)
        context = await self._build_context(user_id)

        # 3. Call LLM (or mock)
        if self._mock_mode:
            llm_response = await self._mock_llm_response(message, context)
        else:
            llm_response = await self._call_llm(message, context)

        # 4. Execute actions from LLM response
        executed_actions = await self._execute_actions(llm_response, user_id)

        # 5. Store assistant message in database
        assistant_message_id = str(uuid.uuid4())
        assistant_created_at = datetime.utcnow().isoformat() + "Z"
        actions_json = json.dumps(executed_actions.model_dump()) if executed_actions else None

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (assistant_message_id, user_id, "assistant", llm_response["message"], actions_json, assistant_created_at),
            )
            conn.commit()

        # 6. Build response
        return ChatResponse(
            message=ChatMessage(
                id=assistant_message_id,
                role="assistant",
                content=llm_response["message"],
                created_at=assistant_created_at,
            ),
            executed_actions=executed_actions,
        )

    async def _build_context(self, user_id: str = "default") -> dict:
        """Build the context for the LLM: portfolio + conversation history."""
        # Import here to avoid circular dependency
        from app.portfolio.service import PortfolioService
        from app.watchlist.service import WatchlistService

        portfolio_service = PortfolioService(self._cache)
        watchlist_service = WatchlistService(self._cache)

        # Get portfolio state
        portfolio = portfolio_service.get_portfolio(user_id)

        # Get watchlist
        watchlist = watchlist_service.get_watchlist(user_id)

        # Get conversation history (last 20 messages)
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, role, content, created_at
                FROM chat_messages
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (user_id,),
            )
            rows = cursor.fetchall()

        history = [
            {"role": row["role"], "content": row["content"]}
            for row in reversed(rows)
        ]

        return {
            "portfolio": portfolio.model_dump(),
            "watchlist": [w.model_dump() for w in watchlist.tickers],
            "history": history,
        }

    async def _mock_llm_response(self, user_message: str, context: dict) -> dict:
        """Return a deterministic mock LLM response for testing."""
        # Simple keyword-based mock responses
        msg_lower = user_message.lower()

        # Mock trading
        if any(word in msg_lower for word in ["buy", "purchase"]):
            ticker = self._extract_ticker(user_message) or "AAPL"
            return {
                "message": f"I'll buy 10 shares of {ticker} at the current price for you.",
                "trades": [
                    {
                        "ticker": ticker,
                        "side": "buy",
                        "quantity": 10,
                    }
                ],
                "watchlist_changes": [],
            }

        # Mock sell
        elif any(word in msg_lower for word in ["sell", "exit"]):
            ticker = self._extract_ticker(user_message) or "AAPL"
            return {
                "message": f"Selling 5 shares of {ticker} at the current price.",
                "trades": [
                    {
                        "ticker": ticker,
                        "side": "sell",
                        "quantity": 5,
                    }
                ],
                "watchlist_changes": [],
            }

        # Mock add to watchlist
        elif any(word in msg_lower for word in ["add", "watch"]):
            ticker = self._extract_ticker(user_message) or "MSFT"
            return {
                "message": f"I've added {ticker} to your watchlist so we can monitor it.",
                "trades": [],
                "watchlist_changes": [
                    {
                        "ticker": ticker,
                        "action": "add",
                    }
                ],
            }

        # Default response
        portfolio_value = context["portfolio"]["total_value"]
        cash = context["portfolio"]["cash_balance"]
        num_positions = len(context["portfolio"]["positions"])

        return {
            "message": f"Your portfolio is currently valued at ${portfolio_value:,.2f} with ${cash:,.2f} in cash. You have {num_positions} position(s). How can I help you today?",
            "trades": [],
            "watchlist_changes": [],
        }

    async def _call_llm(self, user_message: str, context: dict) -> dict:
        """Call the actual LLM via LiteLLM + OpenRouter."""
        # Import litellm here
        try:
            from litellm import completion
        except ImportError:
            # Fallback to mock if litellm not installed
            print("LiteLLM not installed, using mock response")
            return await self._mock_llm_response(user_message, context)

        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

        # Build system prompt
        system_prompt = """You are FinAlly, an AI trading assistant. You help users manage their simulated stock portfolio.

Key capabilities:
- Analyze portfolio composition and P&L
- Execute trades when requested (buy/sell)
- Add/remove tickers from the watchlist
- Provide data-driven insights

Trade rules:
- Only trade if the user asks or agrees
- Validate sufficient cash for buys
- Validate sufficient shares for sells
- Always use the current market price

Respond with valid JSON matching this schema:
{
  "message": "Your conversational response",
  "trades": [{"ticker": "TICKER", "side": "buy/sell", "quantity": N}],
  "watchlist_changes": [{"ticker": "TICKER", "action": "add/remove"}]
}

If no trades or watchlist changes are needed, omit those keys or use empty arrays."""

        # Build messages array
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        for msg in context["history"][-10:]:  # Last 10 messages
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current context
        context_msg = f"""Current portfolio state:
- Cash: ${context["portfolio"]["cash_balance"]:,.2f}
- Total Value: ${context["portfolio"]["total_value"]:,.2f}
- Positions: {len(context["portfolio"]["positions"])} tickers
- Unrealized P&L: ${context["portfolio"]["total_unrealized_pl"]:,.2f}

Watchlist: {', '.join([w["ticker"] for w in context["watchlist"]])}

User message: {user_message}"""

        messages.append({"role": "user", "content": context_msg})

        # Call LLM via OpenRouter.
        # "openrouter/" prefix tells LiteLLM to use the OpenRouter gateway.
        # ":free" suffix selects the free tier of this model.
        try:
            response = completion(
                model="openrouter/meta-llama/llama-3.3-70b-instruct",
                messages=messages,
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            # Fallback to mock on error
            print(f"LLM call failed: {e}, using mock response")
            return await self._mock_llm_response(user_message, context)

    async def _execute_actions(self, llm_response: dict, user_id: str) -> ExecutedActions | None:
        """Execute trades and watchlist changes specified by the LLM."""
        trades = []
        watchlist_changes = []

        # Import services
        from app.portfolio.service import PortfolioService
        from app.watchlist.service import WatchlistService

        portfolio_service = PortfolioService(self._cache)
        watchlist_service = WatchlistService(self._cache)

        # Execute trades
        for trade_spec in llm_response.get("trades", []):
            try:
                executed_trade, _ = portfolio_service.execute_trade(
                    ticker=trade_spec["ticker"],
                    quantity=float(trade_spec["quantity"]),
                    side=trade_spec["side"],
                    user_id=user_id,
                )
                trades.append(
                    ExecutedTrade(
                        id=executed_trade.id,
                        ticker=executed_trade.ticker,
                        side=executed_trade.side,
                        quantity=executed_trade.quantity,
                        price=executed_trade.price,
                        total_value=executed_trade.total_value,
                        executed_at=executed_trade.executed_at,
                    )
                )
            except Exception as e:
                # Log error but continue with other actions
                print(f"Trade execution failed: {e}")

        # Execute watchlist changes
        for change_spec in llm_response.get("watchlist_changes", []):
            try:
                ticker = change_spec["ticker"]
                if change_spec["action"] == "add":
                    await watchlist_service.add_ticker(ticker, user_id)
                    watchlist_changes.append(
                        WatchlistChange(
                            ticker=ticker,
                            action="added",
                            timestamp=datetime.utcnow().isoformat() + "Z",
                        )
                    )
                elif change_spec["action"] == "remove":
                    await watchlist_service.remove_ticker(ticker, user_id)
                    watchlist_changes.append(
                        WatchlistChange(
                            ticker=ticker,
                            action="removed",
                            timestamp=datetime.utcnow().isoformat() + "Z",
                        )
                    )
            except Exception as e:
                # Log error but continue
                print(f"Watchlist change failed: {e}")

        if trades or watchlist_changes:
            return ExecutedActions(
                trades=trades,
                watchlist_changes=watchlist_changes,
            )
        return None

    def _extract_ticker(self, text: str) -> str | None:
        """Extract a ticker symbol from text."""
        # Look for 1-5 uppercase letters
        import re
        match = re.search(r"\b[A-Z]{1,5}\b", text)
        return match.group(0) if match else None
