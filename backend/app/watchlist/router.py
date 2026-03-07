"""Watchlist API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.db import get_db
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
        db = get_db()
        db.init_db()

        try:
            return service.get_watchlist(user_id="default")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch watchlist: {str(e)}",
            )

    @router.post("", response_model=AddToWatchlistResponse, status_code=status.HTTP_200_OK)
    async def add_ticker(request: AddToWatchlistRequest) -> AddToWatchlistResponse:
        """Add a ticker to the watchlist.

        - Ticker must be 1-5 uppercase letters
        - Must not already be in watchlist
        - Ticker immediately starts appearing in price updates
        """
        db = get_db()
        db.init_db()

        try:
            await service.add_ticker(request.ticker, user_id="default")

            # Get updated watchlist
            watchlist = service.get_watchlist(user_id="default")

            return AddToWatchlistResponse(
                status="added",
                ticker=request.ticker,
                watchlist=watchlist,
            )

        except ValueError as e:
            # Business logic validation errors
            if "already in your watchlist" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(e),
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to add ticker: {str(e)}",
            )

    @router.delete("/{ticker}", response_model=RemoveFromWatchlistResponse)
    async def remove_ticker(ticker: str) -> RemoveFromWatchlistResponse:
        """Remove a ticker from the watchlist.

        - Ticker stops appearing in price updates
        - Positions in this ticker are NOT affected
        """
        db = get_db()
        db.init_db()

        try:
            await service.remove_ticker(ticker, user_id="default")

            # Get updated watchlist
            watchlist = service.get_watchlist(user_id="default")

            return RemoveFromWatchlistResponse(
                status="removed",
                ticker=ticker.upper(),
                watchlist=watchlist,
            )

        except ValueError as e:
            # Business logic validation errors
            if "not in your watchlist" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e),
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to remove ticker: {str(e)}",
            )

    return router
