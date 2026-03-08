"""Structured application errors for consistent API error responses."""

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Raised by services/routers to produce a structured JSON error response.

    The global exception handler in main.py converts this to:
        {"error": {"code": ..., "message": ..., "details": ... | null}}
    """

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details
        super().__init__(message)


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------

def invalid_ticker(ticker: str) -> AppError:
    return AppError(
        "INVALID_TICKER",
        "Ticker symbol must be 1-5 uppercase letters",
        status.HTTP_400_BAD_REQUEST,
        {"ticker": ticker, "pattern": "^[A-Z]{1,5}$"},
    )


def invalid_quantity(quantity: float) -> AppError:
    return AppError(
        "INVALID_QUANTITY",
        "Quantity must be between 0.0001 and 1000000",
        status.HTTP_400_BAD_REQUEST,
        {"quantity": quantity},
    )


def invalid_side(side: str) -> AppError:
    return AppError(
        "INVALID_SIDE",
        "Side must be 'buy' or 'sell'",
        status.HTTP_400_BAD_REQUEST,
        {"side": side},
    )


def ticker_not_found(ticker: str) -> AppError:
    return AppError(
        "TICKER_NOT_FOUND",
        f"Ticker '{ticker}' not found in watchlist. Add it to your watchlist first.",
        status.HTTP_404_NOT_FOUND,
        {"ticker": ticker},
    )


def insufficient_cash(ticker: str, quantity: float, price: float, required: float, available: float) -> AppError:
    return AppError(
        "INSUFFICIENT_CASH",
        (
            f"Cannot buy {quantity} shares of {ticker} at ${price:.2f}: "
            f"insufficient cash (have ${available:,.2f}, need ${required:,.2f})"
        ),
        status.HTTP_400_BAD_REQUEST,
        {"ticker": ticker, "quantity": quantity, "price": price, "required": required, "available": available},
    )


def insufficient_shares(ticker: str, requested: float, owned: float) -> AppError:
    return AppError(
        "INSUFFICIENT_SHARES",
        f"Cannot sell {requested} shares of {ticker}: only {owned:.4f} shares owned",
        status.HTTP_400_BAD_REQUEST,
        {"ticker": ticker, "requested": requested, "owned": owned},
    )


def watchlist_exists(ticker: str) -> AppError:
    return AppError(
        "WATCHLIST_EXISTS",
        f"Ticker '{ticker}' is already in your watchlist",
        status.HTTP_409_CONFLICT,
        {"ticker": ticker},
    )


def watchlist_not_found(ticker: str) -> AppError:
    return AppError(
        "WATCHLIST_NOT_FOUND",
        f"Ticker '{ticker}' is not in your watchlist",
        status.HTTP_404_NOT_FOUND,
        {"ticker": ticker},
    )


def internal_error(message: str = "An unexpected error occurred") -> AppError:
    return AppError(
        "INTERNAL_ERROR",
        message,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        None,
    )


# ---------------------------------------------------------------------------
# FastAPI exception handler
# ---------------------------------------------------------------------------

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert AppError into the standard API error response format."""
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )
