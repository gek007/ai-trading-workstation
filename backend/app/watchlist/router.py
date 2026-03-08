"""Watchlist API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.errors import AppError, internal_error
from app.market import MarketDataSource, PriceCache
from app.watchlist.models import (
    AddToWatchlistRequest,
    AddToWatchlistResponse,
    RemoveFromWatchlistResponse,
    WatchlistResponse,
)
from app.watchlist.service import WatchlistService


def create_watchlist_router(
    price_cache: PriceCache,
    market_data_source: MarketDataSource | None = None,
) -> APIRouter:
    """Create the watchlist API router with price cache and market data source dependencies."""

    router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])
    service = WatchlistService(price_cache, market_data_source)

    @router.get("", response_model=WatchlistResponse)
    async def get_watchlist() -> WatchlistResponse:
        """Get the current watchlist with latest prices."""
        try:
            return service.get_watchlist(user_id="default")
        except AppError:
            raise
        except Exception as e:
            raise internal_error(f"Failed to fetch watchlist: {e}") from e

    @router.post("", response_model=AddToWatchlistResponse, status_code=status.HTTP_200_OK)
    async def add_ticker(request: AddToWatchlistRequest) -> AddToWatchlistResponse:
        """Add a ticker to the watchlist.

        Ticker immediately starts appearing in price updates.
        """
        try:
            await service.add_ticker(request.ticker, user_id="default")
            watchlist = service.get_watchlist(user_id="default")
            return AddToWatchlistResponse(
                status="added",
                ticker=request.ticker,
                watchlist=watchlist,
            )
        except AppError:
            raise
        except Exception as e:
            raise internal_error(f"Failed to add ticker: {e}") from e

    @router.delete("/{ticker}", response_model=RemoveFromWatchlistResponse)
    async def remove_ticker(ticker: str) -> RemoveFromWatchlistResponse:
        """Remove a ticker from the watchlist.

        Ticker stops appearing in price updates; positions are NOT affected.
        """
        try:
            await service.remove_ticker(ticker, user_id="default")
            watchlist = service.get_watchlist(user_id="default")
            return RemoveFromWatchlistResponse(
                status="removed",
                ticker=ticker.upper(),
                watchlist=watchlist,
            )
        except AppError:
            raise
        except Exception as e:
            raise internal_error(f"Failed to remove ticker: {e}") from e

    return router
