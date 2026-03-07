# FinAlly Backend - Quick Start Guide

## How to Run the Server

### Method 1: Using the convenience script (Easiest)

```bash
# From the backend directory
python start_server.py
```

Or with uv:
```bash
uv run python start_server.py
```

### Method 2: Direct uvicorn command (Recommended for development)

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Method 3: Python module

```bash
uv run python -m app.main
```

### Method 4: Production mode (no auto-reload)

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Accessing the Server

Once running, open your browser to:

- **Root endpoint**: http://localhost:8000/
- **API documentation**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc
- **SSE stream**: http://localhost:8000/api/stream/prices
- **Health check**: http://localhost:8000/api/health

## Testing the SSE Stream

You can test the Server-Sent Events stream with curl:

```bash
curl -N http://localhost:8000/api/stream/prices
```

Or use a JavaScript EventSource in the browser console:

```javascript
const eventSource = new EventSource('http://localhost:8000/api/stream/prices');
eventSource.addEventListener('message', (e) => {
  console.log(JSON.parse(e.data));
});
```

## Market Data Demo

To see a live terminal dashboard of simulated prices:

```bash
uv run market_data_demo.py
```

This displays a 60-second demo with:
- Live-updating price table
- Color-coded changes (green/red)
- Sparkline charts
- Event log for notable moves (>1% change)

## Configuration

### Using Real Market Data (Massive/Polygon.io API)

1. Get an API key from https://polygon.io/
2. Set the environment variable:

```bash
# Linux/macOS
export MASSIVE_API_KEY="your-api-key-here"

# Windows PowerShell
$env:MASSIVE_API_KEY="your-api-key-here"

# Windows CMD
set MASSIVE_API_KEY=your-api-key-here
```

3. Restart the server

### Using Deterministic Simulator (for testing)

```bash
export MARKET_SIM_SEED=42
```

This makes the simulator produce the same price sequence every time.

## Stopping the Server

Press `Ctrl+C` in the terminal where the server is running.

## Troubleshooting

### Port already in use

If port 8000 is already in use, either:
1. Stop the other process using port 8000, or
2. Use a different port:

```bash
uv run uvicorn app.main:app --port 8001
```

### Import errors

Make sure dependencies are installed:

```bash
uv sync --extra dev
```

### Module not found errors

Make sure you're in the `backend/` directory or use the `-m` flag:

```bash
# From project root
cd backend
uv run uvicorn app.main:app --reload

# OR from project root using -m
uv run python -m backend.app.main
```

## Development Tips

- **Auto-reload**: The `--reload` flag automatically restarts the server when you save changes
- **Logging**: Check the console output for detailed logs about market data updates
- **API testing**: Use the built-in `/docs` endpoint for interactive API testing
- **Monitoring**: The `/api/health` endpoint shows the number of tracked tickers and cache version

## Running Tests

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/market/test_simulator.py

# With coverage
uv run pytest --cov=app --cov-report=html
```

## Default Watchlist

The server starts with these 10 tickers:
- AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

You can modify `DEFAULT_TICKERS` in `app/main.py` to change this.
