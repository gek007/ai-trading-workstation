"""FinAlly Backend - FastAPI Application.

Run the server with:
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Or using the convenience script:
    python -m app.main
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.market import PriceCache, create_market_data_source, create_stream_router
from app.market.seed_prices import SEED_PRICES

# Default watchlist tickers
DEFAULT_TICKERS = list(SEED_PRICES.keys())

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global price cache and market data source
price_cache: PriceCache = PriceCache()
market_data_source = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan manager - starts/stops the market data source."""
    global market_data_source

    # Startup: create and start the market data source
    logger.info("Starting FinAlly backend...")
    logger.info("Default watchlist: %s", DEFAULT_TICKERS)

    market_data_source = create_market_data_source(price_cache)
    await market_data_source.start(DEFAULT_TICKERS)

    logger.info("Market data source started")

    yield

    # Shutdown: stop the market data source
    logger.info("Shutting down...")
    if market_data_source:
        await market_data_source.stop()
        logger.info("Market data source stopped")


# Create FastAPI app with lifespan
app = FastAPI(
    title="FinAlly API",
    description="AI-Powered Trading Workstation Backend",
    version="1.0.0",
    lifespan=lifespan,
)

# Include the SSE streaming router
stream_router = create_stream_router(price_cache)
app.include_router(stream_router)


@app.get("/")
async def root():
    """Root endpoint - API info."""
    return {
        "name": "FinAlly API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "stream": "/api/stream/prices",
            "docs": "/docs",
        },
        "watchlist": DEFAULT_TICKERS,
        "market_data_source": type(market_data_source).__name__ if market_data_source else "not started",
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "tickers_tracked": len(price_cache),
        "cache_version": price_cache.version,
    }


if __name__ == "__main__":
    # Run directly with: python -m app.main
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
