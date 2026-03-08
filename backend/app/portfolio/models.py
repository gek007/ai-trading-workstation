"""Data models for Portfolio API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ============================================================================
# Request Models
# ============================================================================

class TradeRequest(BaseModel):
    """Request to execute a trade."""

    ticker: str = Field(..., min_length=1, max_length=5, pattern="^[a-zA-Z]+$")
    quantity: float = Field(..., gt=0, le=1000000)
    side: Literal["buy", "sell"]

    @field_validator("quantity")
    @classmethod
    def validate_quantity_precision(cls, v: float) -> float:
        """Validate quantity has at most 4 decimal places."""
        if round(v, 4) != v:
            raise ValueError("Quantity must have at most 4 decimal places")
        if v < 0.0001:
            raise ValueError("Quantity must be at least 0.0001")
        return v

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Normalize ticker to uppercase."""
        return v.upper().strip()


# ============================================================================
# Response Models
# ============================================================================

class Position(BaseModel):
    """A single position in the portfolio."""

    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_pl_percent: float


class PortfolioResponse(BaseModel):
    """Portfolio summary with positions."""

    cash_balance: float
    total_value: float
    positions: list[Position]
    total_unrealized_pl: float
    total_unrealized_pl_percent: float


class ExecutedTrade(BaseModel):
    """Details of an executed trade."""

    id: str
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    total_value: float
    executed_at: str


class TradeResponse(BaseModel):
    """Response to a trade execution request."""

    status: Literal["executed"]
    trade: ExecutedTrade
    portfolio: PortfolioResponse


# ============================================================================
# Internal Models (not exposed to API)
# ============================================================================

class PositionRow(BaseModel):
    """Database row for a position."""

    id: str
    user_id: str
    ticker: str
    quantity: float
    avg_cost: float
    updated_at: str


