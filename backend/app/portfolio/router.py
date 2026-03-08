"""Portfolio API endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.errors import AppError, internal_error
from app.market import PriceCache
from app.portfolio.models import PortfolioResponse, TradeRequest, TradeResponse
from app.portfolio.service import PortfolioService


def create_portfolio_router(price_cache: PriceCache) -> APIRouter:
    """Create the portfolio API router with price cache dependency."""

    router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
    service = PortfolioService(price_cache)

    @router.get("", response_model=PortfolioResponse)
    async def get_portfolio() -> PortfolioResponse:
        """Get current portfolio state: positions, cash, total value, and P&L."""
        try:
            return service.get_portfolio(user_id="default")
        except AppError:
            raise
        except Exception as e:
            raise internal_error(f"Failed to fetch portfolio: {e}") from e

    @router.post("/trade", response_model=TradeResponse)
    async def execute_trade(request: TradeRequest) -> TradeResponse:
        """Execute a market order (buy or sell) with instant fill at current price."""
        try:
            executed_trade, portfolio = service.execute_trade(
                ticker=request.ticker,
                quantity=request.quantity,
                side=request.side,
                user_id="default",
            )
            return TradeResponse(status="executed", trade=executed_trade, portfolio=portfolio)
        except AppError:
            raise
        except Exception as e:
            raise internal_error(f"Failed to execute trade: {e}") from e

    return router
