"""FinAlly Backend - FastAPI Application.

Run the server with:
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Or using the convenience script:
    python -m app.main
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.chat import create_chat_router
from app.db import get_db
from app.errors import AppError, app_error_handler
from app.market import PriceCache, create_market_data_source, create_stream_router
from app.market.seed_prices import SEED_PRICES
from app.portfolio import create_portfolio_router
from app.watchlist import create_watchlist_router

# Load .env from the project root (two levels up from this file: backend/app/ -> backend/ -> project root)
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv optional; env vars may be injected by Docker / shell

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
    """FastAPI lifespan manager - initializes DB and starts/stops the market data source."""
    global market_data_source

    logger.info("Starting FinAlly backend...")
    logger.info("Default watchlist: %s", DEFAULT_TICKERS)

    # Initialize database
    db = get_db()
    db.init_db()

    # Start market data source
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

app.add_exception_handler(AppError, app_error_handler)

# CORS — allow the Next.js dev server and any same-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers — watchlist uses a lambda so it resolves the live
# market_data_source at request time, not at module-load time when it is None.
stream_router = create_stream_router(price_cache)
app.include_router(stream_router)

portfolio_router = create_portfolio_router(price_cache)
app.include_router(portfolio_router)

watchlist_router = create_watchlist_router(price_cache, lambda: market_data_source)
app.include_router(watchlist_router)

chat_router = create_chat_router(price_cache)
app.include_router(chat_router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    }


# Serve the compiled Next.js static export from the 'static/' directory.
# This must be mounted AFTER all /api routes so they take priority.
# Gracefully skip when the directory doesn't exist (local backend-only dev).
_static_dir = Path(__file__).parent.parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        """Root endpoint - shown only when the frontend static build is absent."""
        return {
            "name": "FinAlly API",
            "version": "1.0.0",
            "status": "running",
            "note": "Frontend not built yet. Run `npm run build` in frontend/ then copy output to backend/static/.",
            "api_docs": "/docs",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
