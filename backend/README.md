# FinAlly Backend

FastAPI backend for the FinAlly AI Trading Workstation.

## Quick Start

### Running the Server

```bash
# Option 1: Run with uvicorn directly (recommended for development)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Option 2: Run using the Python module
uv run python -m app.main

# Option 3: Run with uvicorn without reload (production-like)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The server will start on `http://localhost:8000`

### Available Endpoints

- `GET /` - API information and status
- `GET /api/health` - Health check
- `GET /api/stream/prices` - SSE stream of live price updates
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

### Market Data Demo

To see a live terminal dashboard of simulated prices:

```bash
uv run market_data_demo.py
```

This will display a 60-second live demo with sparkline charts and price updates.

## Environment Variables

```bash
# Optional: Use real market data from Massive/Polygon.io API
# If not set, the built-in GBM simulator will be used
export MASSIVE_API_KEY="your-api-key-here"

# Optional: Use deterministic simulator for testing
export MARKET_SIM_SEED=42
```

## Structure

- `app/` - Application code
  - `market/` - Market data subsystem
    - `models.py` - PriceUpdate dataclass
    - `cache.py` - Thread-safe price cache
    - `interface.py` - MarketDataSource abstract interface
    - `simulator.py` - GBM-based market simulator
    - `massive_client.py` - Massive/Polygon.io API client
    - `factory.py` - Data source factory
    - `stream.py` - SSE streaming endpoint
    - `seed_prices.py` - Default ticker prices and parameters

- `tests/` - Unit and integration tests
  - `market/` - Market data tests

## Running Tests

```bash
# Install dependencies
uv sync --dev

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test file
uv run pytest tests/market/test_simulator.py

# Run with verbose output
uv run pytest -v
```

## Environment Variables

- `MASSIVE_API_KEY` - Optional. If set, use real market data from Massive API. If not set, use the built-in simulator.

## Development

```bash
# Install dependencies
uv sync --dev

# Run linter
uv run ruff check .

# Format code
uv run ruff format .
```
