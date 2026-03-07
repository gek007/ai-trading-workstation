"""Data models for Chat API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    message: str = Field(..., min_length=1, max_length=1000)


class ChatMessage(BaseModel):
    """A message in the conversation."""

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class ExecutedTrade(BaseModel):
    """A trade that was executed by the LLM."""

    id: str
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    total_value: float
    executed_at: str


class WatchlistChange(BaseModel):
    """A watchlist change made by the LLM."""

    ticker: str
    action: Literal["added", "removed"]
    timestamp: str


class ExecutedActions(BaseModel):
    """Actions that were auto-executed by the LLM."""

    trades: list[ExecutedTrade]
    watchlist_changes: list[WatchlistChange]


class ChatResponse(BaseModel):
    """Response to a chat message."""

    message: ChatMessage
    executed_actions: ExecutedActions | None
