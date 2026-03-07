"""Data models for Watchlist API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AddToWatchlistRequest(BaseModel):
    """Request to add a ticker to the watchlist."""

    ticker: str = Field(..., min_length=1, max_length=5, pattern="^[A-Z]+$")


class WatchlistItem(BaseModel):
    """A watchlist item with current price data."""

    ticker: str
    price: float
    change: float
    change_percent: float
    added_at: str


class WatchlistResponse(BaseModel):
    """Response containing the watchlist."""

    tickers: list[WatchlistItem]


class AddToWatchlistResponse(BaseModel):
    """Response after adding a ticker."""

    status: Literal["added"]
    ticker: str
    watchlist: WatchlistResponse


class RemoveFromWatchlistResponse(BaseModel):
    """Response after removing a ticker."""

    status: Literal["removed"]
    ticker: str
    watchlist: WatchlistResponse
