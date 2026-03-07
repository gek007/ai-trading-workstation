"""Portfolio API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.db import get_db
from app.market import PriceCache
from app.portfolio.models import PortfolioResponse, TradeRequest, TradeResponse
from app.portfolio.service import PortfolioService


def create_portfolio_router(price_cache: PriceCache) -> APIRouter:
    """Create the portfolio API router with price cache dependency."""

    router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
    service = PortfolioService(price_cache)

    @router.get("", response_model=PortfolioResponse)
    async def get_portfolio() -> PortfolioResponse:
        """Get the current portfolio state.

        Returns positions, cash balance, total value, and P&L.
        """
        # Ensure database is initialized
        db = get_db()
        db.init_db()

        try:
            return service.get_portfolio(user_id="default")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch portfolio: {str(e)}",
            )

    @router.post("/trade", response_model=TradeResponse)
    async def execute_trade(request: TradeRequest) -> TradeResponse:
        """Execute a market order (buy or sell).

        - Instant fill at current price
        - No fees, no confirmation dialog
        - Validates sufficient cash (buy) or shares (sell)
        """
        # Ensure database is initialized
        db = get_db()
        db.init_db()

        try:
            executed_trade, portfolio = service.execute_trade(
                ticker=request.ticker,
                quantity=request.quantity,
                side=request.side,
                user_id="default",
            )

            return TradeResponse(
                status="executed",
                trade=executed_trade,
                portfolio=portfolio,
            )

        except ValueError as e:
            # Business logic validation errors
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            # Unexpected errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to execute trade: {str(e)}",
            )

    return router
