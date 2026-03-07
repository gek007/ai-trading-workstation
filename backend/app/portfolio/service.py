"""Portfolio service - business logic for trades and positions."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.db import get_db
from app.market import PriceCache
from app.portfolio.models import (
    ExecutedTrade,
    PortfolioResponse,
    Position,
    PositionRow,
    TradeRow,
)


class PortfolioService:
    """Service for managing portfolio and trades."""

    def __init__(self, price_cache: PriceCache):
        self._cache = price_cache

    def get_portfolio(self, user_id: str = "default") -> PortfolioResponse:
        """Get the current portfolio state for a user."""
        db = get_db()

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Get cash balance
            cursor.execute(
                "SELECT cash_balance FROM users_profile WHERE id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            cash_balance = row["cash_balance"] if row else 10000.0

            # Get all positions
            cursor.execute(
                """
                SELECT id, user_id, ticker, quantity, avg_cost, updated_at
                FROM positions
                WHERE user_id = ?
                ORDER BY ticker
                """,
                (user_id,),
            )
            position_rows = cursor.fetchall()

        # Build response with current prices from cache
        positions = []
        total_unrealized_pl = 0.0
        total_market_value = 0.0

        for row in position_rows:
            pos_row = PositionRow(**dict(row))
            price_update = self._cache.get(pos_row.ticker)
            current_price = price_update.price if price_update else pos_row.avg_cost

            quantity = pos_row.quantity
            avg_cost = pos_row.avg_cost
            market_value = quantity * current_price
            cost_basis = quantity * avg_cost
            unrealized_pl = market_value - cost_basis
            unrealized_pl_percent = (unrealized_pl / cost_basis * 100) if cost_basis > 0 else 0.0

            positions.append(
                Position(
                    ticker=pos_row.ticker,
                    quantity=quantity,
                    avg_cost=round(avg_cost, 2),
                    current_price=round(current_price, 2),
                    market_value=round(market_value, 2),
                    cost_basis=round(cost_basis, 2),
                    unrealized_pl=round(unrealized_pl, 2),
                    unrealized_pl_percent=round(unrealized_pl_percent, 2),
                )
            )

            total_unrealized_pl += unrealized_pl
            total_market_value += market_value

        total_value = cash_balance + total_market_value
        total_unrealized_pl_percent = (
            (total_unrealized_pl / (total_value - cash_balance)) * 100
            if (total_value - cash_balance) > 0
            else 0.0
        )

        return PortfolioResponse(
            cash_balance=round(cash_balance, 2),
            total_value=round(total_value, 2),
            positions=positions,
            total_unrealized_pl=round(total_unrealized_pl, 2),
            total_unrealized_pl_percent=round(total_unrealized_pl_percent, 2),
        )

    def execute_trade(
        self,
        ticker: str,
        quantity: float,
        side: str,
        user_id: str = "default",
    ) -> tuple[ExecutedTrade, PortfolioResponse]:
        """Execute a trade and return the trade details and updated portfolio.

        Raises:
            ValueError: If trade validation fails
        """
        # Get current price from cache
        price_update = self._cache.get(ticker)
        if not price_update:
            raise ValueError(f"Ticker '{ticker}' not found in price cache. Add to watchlist first.")

        current_price = price_update.price
        total_value = quantity * current_price

        db = get_db()

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Get current cash balance
            cursor.execute(
                "SELECT cash_balance FROM users_profile WHERE id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("User profile not found")
            cash_balance = row["cash_balance"]

            # Validate trade
            if side == "buy":
                if total_value > cash_balance:
                    raise ValueError(
                        f"Insufficient cash: need ${total_value:.2f}, have ${cash_balance:.2f}"
                    )
            else:  # sell
                # Check if we have enough shares
                cursor.execute(
                    "SELECT quantity FROM positions WHERE user_id = ? AND ticker = ?",
                    (user_id, ticker),
                )
                pos_row = cursor.fetchone()
                owned_quantity = pos_row["quantity"] if pos_row else 0.0

                if quantity > owned_quantity:
                    raise ValueError(
                        f"Insufficient shares: trying to sell {quantity}, own {owned_quantity}"
                    )

            # Execute trade
            trade_id = str(uuid.uuid4())
            executed_at = datetime.utcnow().isoformat() + "Z"

            cursor.execute(
                """
                INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (trade_id, user_id, ticker, side, quantity, current_price, executed_at),
            )

            # Update or create position
            cursor.execute(
                "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
            pos_row = cursor.fetchone()

            if side == "buy":
                if pos_row:
                    # Update existing position (weighted average cost)
                    old_quantity = pos_row["quantity"]
                    old_avg_cost = pos_row["avg_cost"]
                    new_quantity = old_quantity + quantity
                    total_cost = (old_quantity * old_avg_cost) + (quantity * current_price)
                    new_avg_cost = total_cost / new_quantity

                    cursor.execute(
                        """
                        UPDATE positions
                        SET quantity = ?, avg_cost = ?, updated_at = ?
                        WHERE user_id = ? AND ticker = ?
                        """,
                        (new_quantity, new_avg_cost, executed_at, user_id, ticker),
                    )
                else:
                    # Create new position
                    position_id = str(uuid.uuid4())
                    cursor.execute(
                        """
                        INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (position_id, user_id, ticker, quantity, current_price, executed_at),
                    )

                # Update cash balance
                cursor.execute(
                    "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
                    (cash_balance - total_value, user_id),
                )

            else:  # sell
                old_quantity = pos_row["quantity"]
                new_quantity = old_quantity - quantity

                if new_quantity < 0.0001:  # Position closed (allow for floating point)
                    cursor.execute(
                        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                        (user_id, ticker),
                    )
                else:
                    cursor.execute(
                        "UPDATE positions SET quantity = ?, updated_at = ? WHERE user_id = ? AND ticker = ?",
                        (new_quantity, executed_at, user_id, ticker),
                    )

                # Update cash balance
                cursor.execute(
                    "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
                    (cash_balance + total_value, user_id),
                )

            conn.commit()

        # Create executed trade response
        executed_trade = ExecutedTrade(
            id=trade_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=current_price,
            total_value=total_value,
            executed_at=executed_at,
        )

        # Get updated portfolio
        portfolio = self.get_portfolio(user_id)

        return executed_trade, portfolio
