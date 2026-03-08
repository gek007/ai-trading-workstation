"""Watchlist service - business logic for watchlist management."""

from __future__ import annotations

import uuid

from app.db import get_db
from app.errors import watchlist_exists, watchlist_not_found
from app.market import PriceCache
from app.watchlist.models import WatchlistItem, WatchlistResponse


class WatchlistService:
    """Service for managing watchlist."""

    def __init__(self, price_cache: PriceCache, market_data_source=None):
        self._cache = price_cache
        # Accept either a direct reference or a callable getter (lambda: market_data_source)
        # so the service always resolves the live instance at request time.
        if callable(market_data_source):
            self._get_mds = market_data_source
        else:
            _ref = market_data_source
            self._get_mds = lambda: _ref

    def get_watchlist(self, user_id: str = "default") -> WatchlistResponse:
        """Get the current watchlist with latest prices."""
        db = get_db()

        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT ticker, added_at
                FROM watchlist
                WHERE user_id = ?
                ORDER BY added_at
                """,
                (user_id,),
            )
            rows = cursor.fetchall()

        # Build response with current prices from cache.
        # Always include every ticker; use zeroes when prices haven't arrived yet.
        tickers = []
        for row in rows:
            ticker_symbol = row["ticker"]
            price_update = self._cache.get(ticker_symbol)

            tickers.append(
                WatchlistItem(
                    ticker=ticker_symbol,
                    price=price_update.price if price_update else 0.0,
                    change=price_update.change if price_update else 0.0,
                    change_percent=price_update.change_percent if price_update else 0.0,
                    added_at=row["added_at"],
                )
            )

        return WatchlistResponse(tickers=tickers)

    async def add_ticker(self, ticker: str, user_id: str = "default") -> None:
        """Add a ticker to the watchlist.

        Raises:
            ValueError: If ticker already exists in watchlist
        """
        ticker = ticker.upper().strip()

        db = get_db()

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Check if ticker already exists
            cursor.execute(
                "SELECT id FROM watchlist WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
            if cursor.fetchone():
                raise watchlist_exists(ticker)

            # Add ticker
            watchlist_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO watchlist (id, user_id, ticker, added_at)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (watchlist_id, user_id, ticker),
            )

            conn.commit()

        # Also add to market data source
        mds = self._get_mds()
        if mds:
            await mds.add_ticker(ticker)

    async def remove_ticker(self, ticker: str, user_id: str = "default") -> None:
        """Remove a ticker from the watchlist.

        Raises:
            ValueError: If ticker not found in watchlist
        """
        ticker = ticker.upper().strip()

        db = get_db()

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Check if ticker exists
            cursor.execute(
                "SELECT id FROM watchlist WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
            if not cursor.fetchone():
                raise watchlist_not_found(ticker)

            # Remove ticker
            cursor.execute(
                "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )

            conn.commit()

        # Also remove from market data source
        mds = self._get_mds()
        if mds:
            await mds.remove_ticker(ticker)

    def get_all_tickers(self, user_id: str = "default") -> list[str]:
        """Get all tickers in the watchlist (for market data source)."""
        db = get_db()

        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at",
                (user_id,),
            )
            rows = cursor.fetchall()

        return [row["ticker"] for row in rows]
