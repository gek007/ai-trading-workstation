"""Chat service - LLM integration and chat management."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

from app.chat.models import (
    ChatMessage,
    ChatResponse,
    ExecutedActions,
    ExecutedTrade,
    WatchlistChange,
)
from app.db import get_db
from app.market import PriceCache

logger = logging.getLogger(__name__)


class ChatService:
    """Service for AI-powered chat and trade execution."""

    def __init__(self, price_cache: PriceCache):
        self._cache = price_cache
        self._mock_mode = os.environ.get("LLM_MOCK", "false").strip().lower() == "true"

    async def send_message(self, message: str, user_id: str = "default") -> ChatResponse:
        """Process a user message through the LLM and execute any actions.

        The LLM may auto-execute trades or modify the watchlist based on the conversation.
        Raises RuntimeError if the LLM call fails (when not in mock mode).
        """
        # 1. Store user message in database
        user_message_id = str(uuid.uuid4())
        user_created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

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
            llm_response = self._simple_mock_response(message)
        else:
            llm_response = await self._call_llm(message, context)

        # 4. Execute actions from LLM response
        executed_actions = await self._execute_actions(llm_response, user_id)

        # 5. Store assistant message in database
        assistant_message_id = str(uuid.uuid4())
        assistant_created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        actions_json = json.dumps(executed_actions.model_dump()) if executed_actions else None

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    assistant_message_id,
                    user_id,
                    "assistant",
                    llm_response["message"],
                    actions_json,
                    assistant_created_at,
                ),
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
        from app.portfolio.service import PortfolioService
        from app.watchlist.service import WatchlistService

        portfolio_service = PortfolioService(self._cache)
        watchlist_service = WatchlistService(self._cache)

        portfolio = portfolio_service.get_portfolio(user_id)
        watchlist = watchlist_service.get_watchlist(user_id)

        # Get last 20 messages as conversation history
        db = get_db()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content
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

    def _build_portfolio_context_string(self, context: dict) -> str:
        """Build a formatted portfolio context string for the LLM system prompt."""
        portfolio = context["portfolio"]
        lines = [
            "Portfolio:",
            f"- Cash: ${portfolio['cash_balance']:,.2f}",
            f"- Total Value: ${portfolio['total_value']:,.2f}",
            f"- Unrealized P&L: ${portfolio['total_unrealized_pl']:,.2f}",
        ]

        if portfolio["positions"]:
            lines.append("- Positions:")
            for pos in portfolio["positions"]:
                pl_sign = "+" if pos["unrealized_pl"] >= 0 else ""
                lines.append(
                    f"  {pos['ticker']} x{pos['quantity']} @ ${pos['current_price']:.2f}"
                    f" (cost ${pos['avg_cost']:.2f})"
                    f" = ${pos['market_value']:,.2f}"
                    f" unrealized P&L: {pl_sign}${pos['unrealized_pl']:,.2f}"
                    f" ({pl_sign}{pos['unrealized_pl_percent']:.2f}%)"
                )
        else:
            lines.append("- Positions: none")

        watchlist = context["watchlist"]
        if watchlist:
            wl_items = []
            for item in watchlist:
                change_sign = "+" if item["change_percent"] >= 0 else ""
                wl_items.append(
                    f"{item['ticker']} (${item['price']:.2f}, {change_sign}{item['change_percent']:.2f}%)"
                )
            lines.append(f"Watchlist: {', '.join(wl_items)}")
        else:
            lines.append("Watchlist: empty")

        return "\n".join(lines)

    def _simple_mock_response(self, user_message: str) -> dict:
        """Return a deterministic mock LLM response for E2E testing.

        LLM_MOCK=true mode: simple acknowledgment, no trades or watchlist changes.
        This keeps E2E tests fast and side-effect-free.
        """
        return {
            "message": f"I received your message: '{user_message}'. (Mock mode — no trades executed.)",
            "trades": [],
            "watchlist_changes": [],
        }

    def _keyword_mock_response(self, user_message: str, context: dict) -> dict:
        """Keyword-based mock response used as fallback when LLM API is unavailable."""
        msg_lower = user_message.lower()

        if any(word in msg_lower for word in ["buy", "purchase"]):
            ticker = self._extract_ticker(user_message) or "AAPL"
            return {
                "message": f"I'll buy 10 shares of {ticker} at the current price for you.",
                "trades": [{"ticker": ticker, "side": "buy", "quantity": 10}],
                "watchlist_changes": [],
            }

        if any(word in msg_lower for word in ["sell", "exit"]):
            ticker = self._extract_ticker(user_message) or "AAPL"
            return {
                "message": f"Selling 5 shares of {ticker} at the current price.",
                "trades": [{"ticker": ticker, "side": "sell", "quantity": 5}],
                "watchlist_changes": [],
            }

        if any(word in msg_lower for word in ["add", "watch"]):
            ticker = self._extract_ticker(user_message) or "MSFT"
            return {
                "message": f"I've added {ticker} to your watchlist so we can monitor it.",
                "trades": [],
                "watchlist_changes": [{"ticker": ticker, "action": "add"}],
            }

        portfolio_value = context["portfolio"]["total_value"]
        cash = context["portfolio"]["cash_balance"]
        num_positions = len(context["portfolio"]["positions"])
        return {
            "message": (
                f"Your portfolio is currently valued at ${portfolio_value:,.2f} "
                f"with ${cash:,.2f} in cash. You have {num_positions} position(s). "
                "How can I help you today?"
            ),
            "trades": [],
            "watchlist_changes": [],
        }

    def _parse_llm_response(self, content: str) -> dict:
        """Parse LLM response JSON, handling malformed output gracefully.

        Returns a dict with at least {"message": "...", "trades": [], "watchlist_changes": []}.
        """
        try:
            parsed = json.loads(content)
            # Ensure required keys exist with defaults
            return {
                "message": parsed.get("message", "I processed your request."),
                "trades": parsed.get("trades", []),
                "watchlist_changes": parsed.get("watchlist_changes", []),
            }
        except json.JSONDecodeError:
            logger.warning("LLM returned malformed JSON, attempting partial extraction")
            # Try to extract "message" field from partial JSON
            match = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', content)
            if match:
                msg = match.group(1)
            else:
                msg = "I encountered an issue processing your request. Please try again."
                logger.error("Could not extract message from malformed LLM response")
            return {"message": msg, "trades": [], "watchlist_changes": []}

    async def _call_llm(self, user_message: str, context: dict) -> dict:
        """Call the LLM via LiteLLM + OpenRouter.

        Falls back to keyword-based mock if API key is not configured.
        Raises RuntimeError if the API call fails after key is configured.
        """
        try:
            from litellm import completion
        except ImportError:
            logger.warning("LiteLLM not installed, using keyword mock response")
            return self._keyword_mock_response(user_message, context)

        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            logger.debug("OPENROUTER_API_KEY not set, using keyword mock response")
            return self._keyword_mock_response(user_message, context)

        portfolio_context = self._build_portfolio_context_string(context)

        system_prompt = (
            "You are FinAlly, an AI trading assistant for a simulated trading workstation.\n\n"
            "Your capabilities:\n"
            "- Analyze portfolio composition, risk concentration, and P&L\n"
            "- Suggest trades with clear reasoning\n"
            "- Execute trades when the user asks or agrees (add them to the 'trades' list)\n"
            "- Manage the watchlist proactively (add/remove via 'watchlist_changes')\n"
            "- Be concise and data-driven in your responses\n\n"
            "Current portfolio state:\n"
            f"{portfolio_context}\n\n"
            "ALWAYS respond with valid JSON matching this exact schema:\n"
            '{"message": "conversational response", '
            '"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}], '
            '"watchlist_changes": [{"ticker": "PYPL", "action": "add"}]}\n\n'
            "Use empty arrays [] for trades or watchlist_changes when none are needed."
        )

        messages: list[dict] = [{"role": "system", "content": system_prompt}]

        # Add full conversation history
        for msg in context["history"]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        try:
            response = completion(
                model="openrouter/meta-llama/llama-3.3-70b-instruct",
                messages=messages,
                api_key=api_key,
                api_base="https://openrouter.ai/api/v1",
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return self._parse_llm_response(content)
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise RuntimeError("Failed to process chat message") from e

    async def _execute_actions(self, llm_response: dict, user_id: str) -> ExecutedActions | None:
        """Execute trades and watchlist changes specified by the LLM."""
        from app.portfolio.service import PortfolioService
        from app.watchlist.service import WatchlistService

        portfolio_service = PortfolioService(self._cache)
        watchlist_service = WatchlistService(self._cache)

        trades: list[ExecutedTrade] = []
        watchlist_changes: list[WatchlistChange] = []

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
                logger.warning(f"Trade execution failed for {trade_spec}: {e}")

        for change_spec in llm_response.get("watchlist_changes", []):
            try:
                ticker = change_spec["ticker"]
                action = change_spec["action"]
                now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                if action == "add":
                    await watchlist_service.add_ticker(ticker, user_id)
                    watchlist_changes.append(
                        WatchlistChange(ticker=ticker, action="added", timestamp=now)
                    )
                elif action == "remove":
                    await watchlist_service.remove_ticker(ticker, user_id)
                    watchlist_changes.append(
                        WatchlistChange(ticker=ticker, action="removed", timestamp=now)
                    )
            except Exception as e:
                logger.warning(f"Watchlist change failed for {change_spec}: {e}")

        if trades or watchlist_changes:
            return ExecutedActions(trades=trades, watchlist_changes=watchlist_changes)
        return None

    def _extract_ticker(self, text: str) -> str | None:
        """Extract a ticker symbol from text (1-5 uppercase letters)."""
        match = re.search(r"\b[A-Z]{1,5}\b", text)
        return match.group(0) if match else None
