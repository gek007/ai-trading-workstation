# Market Data Backend — Design & Implementation Reference

This document is the definitive reference for the FinAlly market data subsystem. The implementation lives in `backend/app/market/` and is complete. Use this document to understand how it works and how to integrate with it from other parts of the backend (portfolio, trade execution, watchlist endpoints, FastAPI app lifecycle).

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [File Structure](#2-file-structure)
3. [Data Model — `models.py`](#3-data-model)
4. [Price Cache — `cache.py`](#4-price-cache)
5. [Abstract Interface — `interface.py`](#5-abstract-interface)
6. [Seed Prices & Parameters — `seed_prices.py`](#6-seed-prices--parameters)
7. [GBM Simulator — `simulator.py`](#7-gbm-simulator)
8. [Massive API Client — `massive_client.py`](#8-massive-api-client)
9. [Factory — `factory.py`](#9-factory)
10. [SSE Streaming Endpoint — `stream.py`](#10-sse-streaming-endpoint)
11. [FastAPI Lifecycle Integration](#11-fastapi-lifecycle-integration)
12. [Watchlist Coordination](#12-watchlist-coordination)
13. [Reading Prices from the Cache](#13-reading-prices-from-the-cache)
14. [SSE Wire Format](#14-sse-wire-format)
15. [Configuration Reference](#15-configuration-reference)
16. [Error Handling](#16-error-handling)
17. [Testing](#17-testing)

---

## 1. Architecture Overview

```
Environment
  MASSIVE_API_KEY set? ──Yes──> MassiveDataSource  ─┐
                └──No──> SimulatorDataSource  ─┘
                                                     │ writes to
                                               PriceCache (in-memory, thread-safe)
                                                     │
                         ┌───────────────────────────┤
                         │                           │
                   SSE stream               portfolio/trade
                /api/stream/prices          endpoints read
                   (frontend)               current prices
```

**Three key design principles:**

1. **Strategy pattern** — `SimulatorDataSource` and `MassiveDataSource` both implement `MarketDataSource`. All downstream code is source-agnostic. Swapping sources requires only changing the factory call.

2. **Cache as single point of truth** — producers (simulator or Massive) write to `PriceCache`; all consumers (SSE, portfolio, trade execution) read from it. No direct coupling between producer and consumer.

3. **One background task** — a single asyncio task runs the update loop. It is started at app startup and stopped at shutdown via FastAPI's lifespan handler.

---

## 2. File Structure

```
backend/
  app/
    market/
      __init__.py         # Public re-exports (see section below)
      models.py           # PriceUpdate dataclass
      cache.py            # PriceCache (thread-safe in-memory store)
      interface.py        # MarketDataSource abstract base class
      seed_prices.py      # Seed prices, GBM params, correlation groups
      simulator.py        # GBMSimulator + SimulatorDataSource
      massive_client.py   # MassiveDataSource (Polygon.io REST poller)
      factory.py          # create_market_data_source() factory
      stream.py           # create_stream_router() SSE endpoint factory
  tests/
    market/
      test_models.py
      test_cache.py
      test_simulator.py
      test_simulator_source.py
      test_factory.py
      test_massive.py
```

### Public Imports

Everything downstream code needs is re-exported from `app.market`:

```python
from app.market import (
    PriceUpdate,              # The data model
    PriceCache,               # The in-memory store
    MarketDataSource,         # The abstract interface (for type hints)
    create_market_data_source, # The factory
    create_stream_router,     # The SSE router factory
)
```

---

## 3. Data Model

**File:** `backend/app/market/models.py`

`PriceUpdate` is an immutable frozen dataclass. It is the only type that crosses the boundary between the market data layer and the rest of the application.

```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    ticker: str
    price: float            # Current price, rounded to 2 decimal places
    previous_price: float   # Price at the last update, rounded to 2 decimal places
    timestamp: float        # Unix seconds (time.time())

    @property
    def change(self) -> float:
        """Absolute price change (price - previous_price), 4 decimal places."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Percentage change, 4 decimal places. Returns 0.0 if previous_price is 0."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat'."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
        }
```

**Key points:**
- `frozen=True` makes it hashable and prevents accidental mutation. Always create a new `PriceUpdate` — never modify one.
- `slots=True` reduces memory overhead (important when thousands of updates flow through).
- `price` and `previous_price` are pre-rounded to 2 decimal places by `PriceCache.update()` before the object is created. Do not round again at the call site.
- `direction` uses `"flat"` (not `"unchanged"`). The SSE wire format (section 14) documents the exact values sent to the frontend.
- The `timestamp` field has `default_factory=time.time`, so if you create a `PriceUpdate` directly in tests, omitting `timestamp` gives the current time automatically.

**Usage example:**

```python
update = cache.get("AAPL")
if update:
    print(f"{update.ticker}: ${update.price:.2f} ({update.direction})")
    print(f"  Change: {update.change:+.4f} ({update.change_percent:+.4f}%)")
    print(f"  Serialized: {update.to_dict()}")
```

---

## 4. Price Cache

**File:** `backend/app/market/cache.py`

The `PriceCache` is the shared state between the market data producer and all consumers. It is thread-safe via a `threading.Lock`.

```python
class PriceCache:
    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically incremented on every update

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Write a new price. Returns the PriceUpdate that was stored.

        - Rounds price to 2 decimal places.
        - Sets previous_price from the existing entry (or price itself on first update).
        - Increments version.
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        """Get the latest PriceUpdate for a ticker, or None."""
        with self._lock:
            return self._prices.get(ticker)

    def get_price(self, ticker: str) -> float | None:
        """Convenience: return just the price float, or None."""
        update = self.get(ticker)
        return update.price if update else None

    def get_all(self) -> dict[str, PriceUpdate]:
        """Shallow copy of all current prices. Safe to iterate without the lock."""
        with self._lock:
            return dict(self._prices)

    def remove(self, ticker: str) -> None:
        """Remove a ticker. Called when user removes from watchlist."""
        with self._lock:
            self._prices.pop(ticker, None)

    @property
    def version(self) -> int:
        """Monotonic counter. SSE streaming uses this for change detection."""
        return self._version

    def __len__(self) -> int: ...
    def __contains__(self, ticker: str) -> bool: ...
```

### Version-Based Change Detection

The `version` property is critical for efficient SSE streaming. Instead of sending a snapshot every 500ms regardless of whether prices changed, the SSE generator only emits an event when `version` has changed since the last emit. This avoids redundant data during the brief startup window before the simulator has run its first step.

```python
last_version = -1
while True:
    current_version = price_cache.version
    if current_version != last_version:
        last_version = current_version
        prices = price_cache.get_all()
        if prices:
            yield build_sse_event(prices)
    await asyncio.sleep(0.5)
```

### Thread Safety Note

The Massive API client runs its HTTP calls in a thread (via `asyncio.to_thread`). The GBM simulator runs in the asyncio event loop. Both write to the same `PriceCache`. The `Lock` in `PriceCache.update()` makes this safe.

On CPython (standard Python), the GIL provides an additional safety net, but the explicit lock is the correct approach and will work correctly on no-GIL Python builds (PEP 703).

---

## 5. Abstract Interface

**File:** `backend/app/market/interface.py`

```python
class MarketDataSource(ABC):
    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates. Call once at app startup."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task. Safe to call multiple times."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker. Also clears it from PriceCache."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the current list of tracked tickers."""
```

**Lifecycle contract:**
1. Create the source with the factory (unstarted)
2. Call `await source.start(initial_tickers)` — begins the background task
3. Call `await source.add_ticker(t)` / `await source.remove_ticker(t)` as watchlist changes
4. Call `await source.stop()` at app shutdown

`start()` must be called exactly once. Calling it twice is undefined behavior.
`stop()` is idempotent — calling it multiple times is safe.

---

## 6. Seed Prices & Parameters

**File:** `backend/app/market/seed_prices.py`

These constants configure the GBM simulator's starting state. They are the only place where per-ticker parameters are defined.

```python
# Starting prices for the default 10-ticker watchlist
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00,
    "GOOGL": 175.00,
    "MSFT": 420.00,
    "AMZN": 185.00,
    "TSLA": 250.00,
    "NVDA": 800.00,
    "META": 500.00,
    "JPM": 195.00,
    "V": 280.00,
    "NFLX": 600.00,
}

# Per-ticker GBM parameters
# sigma: annualized volatility (standard deviation of log returns)
# mu: annualized drift (expected return)
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"sigma": 0.22, "mu": 0.05},  # Blue chip, moderate vol
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT":  {"sigma": 0.20, "mu": 0.05},  # Lowest vol of the tech names
    "AMZN":  {"sigma": 0.28, "mu": 0.05},
    "TSLA":  {"sigma": 0.50, "mu": 0.03},  # High vol, lower drift
    "NVDA":  {"sigma": 0.40, "mu": 0.08},  # High vol, strong upward drift
    "META":  {"sigma": 0.30, "mu": 0.05},
    "JPM":   {"sigma": 0.18, "mu": 0.04},  # Low vol (bank)
    "V":     {"sigma": 0.17, "mu": 0.04},  # Lowest vol overall (payments)
    "NFLX":  {"sigma": 0.35, "mu": 0.05},
}

# Default for dynamically added tickers (not in TICKER_PARAMS)
DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}

# Sector groups used to build the correlation matrix
CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech":    {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

# Pairwise correlation coefficients
INTRA_TECH_CORR    = 0.6  # Tech stocks move together
INTRA_FINANCE_CORR = 0.5  # Finance stocks move together
CROSS_GROUP_CORR   = 0.3  # Different sectors, or unknown tickers
TSLA_CORR          = 0.3  # TSLA is in tech set but treated independently
```

**To add a new default ticker:** add it to `SEED_PRICES` and `TICKER_PARAMS`. If it belongs to an existing sector, add it to `CORRELATION_GROUPS`. Otherwise it will use `CROSS_GROUP_CORR = 0.3` with all others.

**For dynamically added tickers** (added via watchlist at runtime): if not in `SEED_PRICES`, the simulator assigns a random seed price in the range `$50–$300`. If not in `TICKER_PARAMS`, it uses `DEFAULT_PARAMS`.

---

## 7. GBM Simulator

**File:** `backend/app/market/simulator.py`

Two classes: `GBMSimulator` (the math engine) and `SimulatorDataSource` (the `MarketDataSource` implementation that wraps it in an async loop).

### 7.1 GBM Math

Geometric Brownian Motion models stock price evolution as a lognormal process. At each time step:

```
S(t+dt) = S(t) * exp((mu - sigma²/2) * dt + sigma * sqrt(dt) * Z)
```

Where:
- `S(t)` — current price
- `mu` — annualized drift (e.g., `0.05` = 5% expected annual return)
- `sigma` — annualized volatility (e.g., `0.22` = 22% annualized std dev)
- `dt` — time step as a fraction of a trading year
- `Z` — standard normal random variable N(0,1)

For 500ms ticks over a 252-day, 6.5-hour trading year:

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800 seconds
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ~8.48e-8
```

This tiny `dt` produces sub-cent moves per tick — which accumulate naturally into realistic intraday ranges. With `sigma=0.22` (AAPL), the expected per-tick standard deviation of the price move is:

```
sigma * sqrt(dt) * price ≈ 0.22 * sqrt(8.48e-8) * 190 ≈ $0.012
```

### 7.2 Correlated Moves

Real stocks move together within sectors. We generate correlated random draws using the Cholesky decomposition of the correlation matrix.

```python
# Build the n×n correlation matrix
corr = np.eye(n)
for i in range(n):
    for j in range(i+1, n):
        rho = _pairwise_correlation(tickers[i], tickers[j])
        corr[i, j] = corr[j, i] = rho

# Decompose: corr = L @ L.T
cholesky = np.linalg.cholesky(corr)

# At each step: generate independent draws, then apply L to correlate them
z_independent = np.random.standard_normal(n)
z_correlated = cholesky @ z_independent
```

Pairwise correlation rules:
- TSLA with any other ticker: `0.3` (TSLA is in the tech group but treated as independent)
- Two tech tickers (excluding TSLA): `0.6`
- Two finance tickers: `0.5`
- Cross-sector or unknown: `0.3`

### 7.3 Random Events

Every step, each ticker has a `0.1%` chance of a sudden 2–5% shock (up or down):

```python
if random.random() < 0.001:  # event_probability
    shock_magnitude = random.uniform(0.02, 0.05)
    shock_sign = random.choice([-1, 1])
    self._prices[ticker] *= 1 + shock_magnitude * shock_sign
```

With 10 tickers at 2 steps/second: `0.001 * 10 * 2 = 0.02` events/second on average = roughly one event somewhere in the watchlist every 50 seconds. This keeps the dashboard visually interesting without destabilizing prices.

### 7.4 GBMSimulator Class

```python
class GBMSimulator:
    DEFAULT_DT = 0.5 / (252 * 6.5 * 3600)  # ~8.48e-8

    def __init__(
        self,
        tickers: list[str],
        dt: float = DEFAULT_DT,
        event_probability: float = 0.001,
    ) -> None:
        # Initializes prices, params, and builds Cholesky matrix
        ...

    def step(self) -> dict[str, float]:
        """Advance all tickers one time step. Returns {ticker: new_price}.

        Hot path — called every 500ms. Uses numpy for the normal draws
        and matrix multiplication; per-ticker loop handles GBM math.
        """

    def add_ticker(self, ticker: str) -> None:
        """Add a ticker and rebuild the Cholesky matrix. O(n²), n < 50."""

    def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker and rebuild the Cholesky matrix."""

    def get_price(self, ticker: str) -> float | None:
        """Current simulated price for a ticker."""

    def get_tickers(self) -> list[str]:
        """List of currently tracked tickers."""
```

### 7.5 SimulatorDataSource Class

```python
class SimulatorDataSource(MarketDataSource):
    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,     # seconds between steps
        event_probability: float = 0.001, # per-ticker per-step shock probability
    ) -> None: ...

    async def start(self, tickers: list[str]) -> None:
        """Creates GBMSimulator, seeds the cache with initial prices,
        then starts the background asyncio task."""
        self._sim = GBMSimulator(tickers=tickers, event_probability=self._event_prob)
        # Seed the cache immediately so the SSE endpoint has data from tick 0
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")

    async def _run_loop(self) -> None:
        """Core loop: step simulator, write to cache, sleep."""
        while True:
            try:
                prices = self._sim.step()
                for ticker, price in prices.items():
                    self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

The `except Exception` in `_run_loop` is intentional: a bug in the GBM math should log an error but not crash the server. The loop continues and will retry on the next interval.

---

## 8. Massive API Client

**File:** `backend/app/market/massive_client.py`

Used when `MASSIVE_API_KEY` is set. Polls the Polygon.io REST API (via the `massive` Python package) for real market data.

### 8.1 API Used

Single endpoint: `GET /v2/snapshot/locale/us/markets/stocks/tickers`

This returns current price data for multiple tickers in one API call — critical for staying within the free-tier rate limit of 5 requests/minute.

```python
# Synchronous Polygon.io client call (runs in thread pool)
snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "GOOGL", "MSFT", ...],
)

for snap in snapshots:
    price = snap.last_trade.price
    timestamp = snap.last_trade.timestamp / 1000.0  # ms → seconds
    cache.update(ticker=snap.ticker, price=price, timestamp=timestamp)
```

### 8.2 Poll Interval

```
Free tier  (5 req/min):  poll_interval = 15.0 seconds (default)
Paid tier (unlimited):   poll_interval = 2–5 seconds (change at init)
```

```python
# Use a faster poll interval for paid accounts
source = MassiveDataSource(
    api_key=api_key,
    price_cache=cache,
    poll_interval=5.0,  # 5-second intervals for paid tier
)
```

### 8.3 MassiveDataSource Class

```python
class MassiveDataSource(MarketDataSource):
    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
    ) -> None: ...

    async def start(self, tickers: list[str]) -> None:
        """Initialize the REST client, do an immediate first poll
        (so the cache isn't empty at startup), then start the poll loop."""
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = list(tickers)
        await self._poll_once()  # Immediate first poll
        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")

    async def _poll_loop(self) -> None:
        """Sleep, then poll. First poll already happened in start()."""
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        """Execute one poll cycle. Catches all exceptions — the loop continues
        on API errors (401, 429, network timeouts, etc.)."""
        if not self._tickers or not self._client:
            return
        try:
            # RESTClient is synchronous — run in thread pool to avoid
            # blocking the asyncio event loop
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
            for snap in snapshots:
                try:
                    price = snap.last_trade.price
                    timestamp = snap.last_trade.timestamp / 1000.0
                    self._cache.update(
                        ticker=snap.ticker,
                        price=price,
                        timestamp=timestamp,
                    )
                except (AttributeError, TypeError) as e:
                    # Malformed snapshot: log and skip, don't fail the whole poll
                    logger.warning("Skipping snapshot for %s: %s",
                                   getattr(snap, "ticker", "???"), e)
        except Exception as e:
            logger.error("Massive poll failed: %s", e)

    def _fetch_snapshots(self) -> list:
        """Synchronous REST call. Runs in asyncio.to_thread()."""
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

### 8.4 Massive API Error Reference

| HTTP Status | Meaning | Behavior |
|---|---|---|
| `401` | Bad API key | Logged as error; retry on next interval |
| `403` | Insufficient plan | Logged as error; retry on next interval |
| `429` | Rate limit exceeded | Logged as error; retry on next interval |
| `5xx` | Server error | Logged as error; retry on next interval |

The `massive` client has built-in retry (3 attempts) for 5xx errors. `_poll_once` catches anything that escapes the client and keeps the loop running.

### 8.5 Market Hours Behavior

- During market hours: `last_trade.price` reflects the latest trade price, updated frequently.
- After hours / weekends: `last_trade.price` reflects the last trade before close. Prices appear frozen — this is correct behavior. The frontend will see no direction changes.
- The `day` object (OHLC, volume, change) resets at market open. During pre-market, values may reflect the previous session.

---

## 9. Factory

**File:** `backend/app/market/factory.py`

```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Select the appropriate data source based on environment.

    Reads MASSIVE_API_KEY from the environment:
      - Set and non-empty → MassiveDataSource (real Polygon.io data)
      - Not set or empty  → SimulatorDataSource (GBM simulation, default)

    Returns an unstarted source. Caller must await source.start(tickers).
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(price_cache=price_cache)
```

The factory reads `MASSIVE_API_KEY` at call time (not import time), so setting the env var before the app starts is sufficient. Both sources are always imported at module load time — there is no lazy import.

---

## 10. SSE Streaming Endpoint

**File:** `backend/app/market/stream.py`

The SSE endpoint is created via a factory function that closes over the `PriceCache`:

```python
router = APIRouter(prefix="/api/stream", tags=["streaming"])

def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Register the /prices SSE endpoint on the router and return it."""

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Prevent nginx buffering
            },
        )

    return router
```

The generator loop:

```python
async def _generate_events(
    price_cache: PriceCache,
    request: Request,
    interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    # Tell the browser to reconnect after 1 second if the connection drops
    yield "retry: 1000\n\n"

    last_version = -1

    while True:
        if await request.is_disconnected():
            break

        current_version = price_cache.version
        if current_version != last_version:
            last_version = current_version
            prices = price_cache.get_all()
            if prices:
                data = {ticker: update.to_dict() for ticker, update in prices.items()}
                yield f"data: {json.dumps(data)}\n\n"

        await asyncio.sleep(interval)
```

**Important implementation details:**

1. The `retry: 1000\n\n` directive sent on connect tells the browser's `EventSource` to wait 1 second before reconnecting if the connection drops. This is the built-in auto-reconnection mechanism.

2. Version-based change detection (`last_version != current_version`) means we only emit an event when prices have actually changed. On a fresh start with no clients, the simulator runs independently of whether anyone is connected.

3. `X-Accel-Buffering: no` disables nginx buffering if the app is behind an nginx reverse proxy. Without this, events get buffered and the client sees bursts instead of a stream.

4. `request.is_disconnected()` is checked every `interval` seconds. When a client closes the browser tab, the FastAPI/Starlette ASGI layer detects the TCP disconnect and `is_disconnected()` returns `True` on the next check.

---

## 11. FastAPI Lifecycle Integration

The market data system must be wired into FastAPI's lifespan handler. Here is the complete pattern for `backend/app/main.py`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.market import PriceCache, create_market_data_source, create_stream_router

# --- Application State ---

price_cache = PriceCache()
market_source = None  # Set during lifespan startup

# --- Lifespan Handler ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    global market_source

    # Load initial tickers from the database
    initial_tickers = await get_watchlist_tickers()  # Your DB call

    # Create and start the market data source
    market_source = create_market_data_source(price_cache)
    await market_source.start(initial_tickers)

    yield  # App is running — handle requests

    # Shutdown: cancel the background task
    await market_source.stop()

# --- App Setup ---

app = FastAPI(lifespan=lifespan)

# Register the SSE router (injects price_cache via closure)
app.include_router(create_stream_router(price_cache))

# Register other routers
app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(chat_router)

# Serve the static Next.js export (must come last)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

### Making the Cache Available to Other Routes

Other routers (portfolio, trade, watchlist) need access to `price_cache` and `market_source`. Use FastAPI's dependency injection or pass them at router creation time. The simplest approach for a single-user app is module-level instances:

```python
# app/dependencies.py
from app.market import PriceCache, MarketDataSource

# Module-level singletons (initialized in lifespan)
price_cache: PriceCache = PriceCache()
market_source: MarketDataSource | None = None
```

```python
# app/main.py
from app import dependencies

@asynccontextmanager
async def lifespan(app: FastAPI):
    dependencies.market_source = create_market_data_source(dependencies.price_cache)
    await dependencies.market_source.start(initial_tickers)
    yield
    await dependencies.market_source.stop()
```

```python
# app/routes/portfolio.py
from app.dependencies import price_cache

@router.get("/api/portfolio")
async def get_portfolio():
    aapl_price = price_cache.get_price("AAPL")
    # ... build portfolio response
```

---

## 12. Watchlist Coordination

When the user adds or removes a ticker from the watchlist (via `POST /api/watchlist` or `DELETE /api/watchlist/{ticker}`), the market data source must be updated in the same request handler:

```python
# app/routes/watchlist.py
from app.dependencies import price_cache, market_source

@router.post("/api/watchlist")
async def add_to_watchlist(body: AddToWatchlistRequest):
    ticker = body.ticker.upper()

    # 1. Write to the database
    await db_add_watchlist_ticker(ticker)

    # 2. Tell the market data source to start tracking this ticker
    #    This seeds the cache immediately (simulator) or on next poll (Massive)
    await market_source.add_ticker(ticker)

    # 3. Return the updated watchlist with current prices
    return build_watchlist_response(price_cache)


@router.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str):
    ticker = ticker.upper()

    # 1. Remove from database
    await db_remove_watchlist_ticker(ticker)

    # 2. Tell the market data source to stop tracking it
    #    This also removes it from PriceCache
    await market_source.remove_ticker(ticker)

    return build_watchlist_response(price_cache)
```

**Timing guarantees:**

- `SimulatorDataSource.add_ticker()`: seeds the cache **immediately** with the seed price. The ticker appears in the SSE stream on the very next event.
- `MassiveDataSource.add_ticker()`: adds the ticker to the polling list. It appears in the cache **on the next poll cycle** (up to 15 seconds on the free tier). During this window, `price_cache.get("NEW_TICKER")` returns `None`.

Callers should handle the case where a newly-added ticker has no price yet:

```python
def build_watchlist_response(cache: PriceCache) -> dict:
    tickers = []
    for ticker in db_watchlist:
        update = cache.get(ticker)
        tickers.append({
            "ticker": ticker,
            "price": update.price if update else None,
            "change": update.change if update else None,
            "change_percent": update.change_percent if update else None,
        })
    return {"tickers": tickers}
```

---

## 13. Reading Prices from the Cache

Other backend subsystems (portfolio valuation, trade execution) read from the cache. Here are the exact patterns:

### Get a single price (trade execution)

```python
from app.dependencies import price_cache

def get_current_price(ticker: str) -> float:
    """Get the current price for trade execution. Raises if price unavailable."""
    price = price_cache.get_price(ticker)
    if price is None:
        raise ValueError(f"No price available for {ticker}")
    return price

# Usage in trade handler:
async def execute_trade(ticker: str, quantity: float, side: str):
    price = get_current_price(ticker)  # Raises if unknown
    cost = quantity * price
    if side == "buy" and cost > cash_balance:
        raise InsufficientCashError(...)
    # ... proceed with trade
```

### Get all prices (portfolio valuation)

```python
def calculate_portfolio_value(positions: list[Position]) -> dict:
    """Calculate total portfolio value using current cached prices."""
    all_prices = price_cache.get_all()  # Single lock acquisition for all prices

    total_market_value = 0.0
    for position in positions:
        update = all_prices.get(position.ticker)
        if update:
            market_value = position.quantity * update.price
            total_market_value += market_value

    return {
        "total_market_value": round(total_market_value, 2),
        "cash_balance": cash_balance,
        "total_value": round(total_market_value + cash_balance, 2),
    }
```

### Get prices for watchlist display

```python
def build_watchlist_with_prices(watchlist_tickers: list[str]) -> list[dict]:
    all_prices = price_cache.get_all()
    return [
        {
            "ticker": ticker,
            "price": all_prices[ticker].price if ticker in all_prices else None,
            "change": all_prices[ticker].change if ticker in all_prices else None,
            "change_percent": all_prices[ticker].change_percent if ticker in all_prices else None,
        }
        for ticker in watchlist_tickers
    ]
```

---

## 14. SSE Wire Format

The SSE stream emits events at ~500ms intervals. The wire format is:

```
retry: 1000\n\n                  ← Sent once on connect; browser reconnect delay (ms)

data: {JSON payload}\n\n         ← Emitted whenever prices have changed
```

The JSON payload is a **dict keyed by ticker symbol** (not an array):

```json
{
  "AAPL": {
    "ticker": "AAPL",
    "price": 190.50,
    "previous_price": 190.25,
    "timestamp": 1736940645.123,
    "change": 0.25,
    "change_percent": 0.1314,
    "direction": "up"
  },
  "GOOGL": {
    "ticker": "GOOGL",
    "price": 175.30,
    "previous_price": 175.40,
    "timestamp": 1736940645.123,
    "change": -0.10,
    "change_percent": -0.057,
    "direction": "down"
  },
  "MSFT": {
    "ticker": "MSFT",
    "price": 420.00,
    "previous_price": 420.00,
    "timestamp": 1736940645.123,
    "change": 0.0,
    "change_percent": 0.0,
    "direction": "flat"
  }
}
```

**Field types:**
- `ticker` — string, uppercase
- `price`, `previous_price` — float, 2 decimal places
- `timestamp` — float, Unix seconds (not milliseconds)
- `change` — float, 4 decimal places (can be negative)
- `change_percent` — float, 4 decimal places (can be negative)
- `direction` — `"up"` | `"down"` | `"flat"` (note: `"flat"`, not `"unchanged"`)

**Events use no `event:` name** — they are anonymous SSE events, which the browser's `EventSource` receives via the `onmessage` handler.

**Frontend JavaScript (canonical example):**

```javascript
const es = new EventSource('/api/stream/prices');

es.onmessage = (event) => {
  const prices = JSON.parse(event.data);
  // prices is an object: { "AAPL": {...}, "GOOGL": {...}, ... }
  for (const [ticker, update] of Object.entries(prices)) {
    updateTickerDisplay(ticker, update);
  }
};

es.onerror = () => {
  // EventSource auto-reconnects (using the retry: 1000 directive)
  // Update connection status indicator to "reconnecting"
};
```

**Note on API_CONTRACTS.md:** `API_CONTRACTS.md` specifies the SSE format with a named `event: price_update` and an array payload `{"tickers": [...]}`. The actual implementation uses anonymous events and a dict payload keyed by ticker. The implementation takes precedence. The frontend should use `onmessage` (anonymous events) and iterate `Object.entries(prices)` (dict), not `data.tickers` (array).

---

## 15. Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `MASSIVE_API_KEY` | (not set) | When set and non-empty, enables the Polygon.io real data source. |
| `MARKET_SIM_SEED` | (not set) | Integer seed for `numpy.random` and `random`. When set, produces a deterministic price sequence. Use in tests. |

### Deterministic Mode (Testing)

To make simulator output reproducible:

```bash
MARKET_SIM_SEED=42 uvicorn app.main:app
```

In `main.py` (or wherever the lifespan runs):

```python
import os, random
import numpy as np

sim_seed = os.environ.get("MARKET_SIM_SEED")
if sim_seed:
    seed = int(sim_seed)
    random.seed(seed)
    np.random.seed(seed)
    logger.info("Simulator using deterministic seed: %d", seed)
```

Set this **before** `create_market_data_source()` is called. The seed affects all subsequent calls to `random.random()` and `np.random.standard_normal()` in the simulator, making every price path identical across runs.

### Simulator Tuning

`SimulatorDataSource` accepts optional constructor parameters:

```python
# Faster updates (e.g., for testing faster SSE behavior)
source = SimulatorDataSource(
    price_cache=cache,
    update_interval=0.1,      # 10 updates/second instead of 2
    event_probability=0.0,    # No random events (useful for stable test assertions)
)
```

### Massive Poll Interval

```python
# For paid Polygon.io accounts with higher rate limits
source = MassiveDataSource(
    api_key=api_key,
    price_cache=cache,
    poll_interval=5.0,        # 5-second intervals (12 req/min)
)
```

---

## 16. Error Handling

### Simulator

The `_run_loop` catches all exceptions from `GBMSimulator.step()` and continues:

```python
async def _run_loop(self) -> None:
    while True:
        try:
            prices = self._sim.step()
            for ticker, price in prices.items():
                self._cache.update(ticker=ticker, price=price)
        except Exception:
            logger.exception("Simulator step failed")
        await asyncio.sleep(self._interval)
```

In practice, `step()` can fail if the Cholesky decomposition fails (e.g., a pathological correlation matrix introduced by a buggy ticker). The log entry will help diagnose this. The loop recovers automatically on the next tick.

### Massive API

`_poll_once` catches all exceptions including network errors, 401/429 HTTP errors, and malformed responses:

```python
async def _poll_once(self) -> None:
    try:
        snapshots = await asyncio.to_thread(self._fetch_snapshots)
        for snap in snapshots:
            try:
                self._cache.update(ticker=snap.ticker, price=snap.last_trade.price, ...)
            except (AttributeError, TypeError) as e:
                logger.warning("Skipping snapshot for %s: %s", ...)
    except Exception as e:
        logger.error("Massive poll failed: %s", e)
```

A poll failure means prices are stale until the next successful poll. The SSE stream continues sending the last-known prices. The frontend receives data but with a frozen timestamp — a future enhancement could detect staleness based on timestamp age.

### SSE Generator

The generator handles `asyncio.CancelledError` for clean shutdown:

```python
try:
    while True:
        if await request.is_disconnected():
            break
        # ... emit events
except asyncio.CancelledError:
    logger.info("SSE stream cancelled")
```

When the FastAPI app shuts down, asyncio cancels all running coroutines, including active SSE generator tasks.

---

## 17. Testing

### Test Infrastructure

```bash
cd backend
uv sync --extra dev              # Install test dependencies
uv run --extra dev pytest -v     # Run all tests
uv run --extra dev pytest --cov=app  # With coverage report
uv run --extra dev ruff check app/ tests/  # Lint
```

### Test Coverage Summary

| Module | Coverage | Notes |
|---|---|---|
| `models.py` | 100% | All properties and serialization |
| `cache.py` | 100% | All methods including thread safety |
| `interface.py` | 100% | ABC (no logic to test) |
| `seed_prices.py` | 100% | Constants (no logic) |
| `factory.py` | 100% | Both branches (with/without API key) |
| `simulator.py` | 98% | All paths except exception log line |
| `massive_client.py` | 56% | REST methods mocked; expected with no real API |
| `stream.py` | 31% | SSE generator requires ASGI test client |

### Writing Tests Against the Cache

```python
# tests/market/test_cache.py pattern
from app.market import PriceCache, PriceUpdate

def test_update_and_get():
    cache = PriceCache()
    update = cache.update("AAPL", 190.50)

    assert update.ticker == "AAPL"
    assert update.price == 190.50
    assert update.previous_price == 190.50  # First update: previous == price
    assert update.direction == "flat"

    update2 = cache.update("AAPL", 191.00)
    assert update2.previous_price == 190.50
    assert update2.direction == "up"
    assert cache.version == 2
```

### Testing with a Controlled Simulator

```python
# Use event_probability=0.0 to disable random events for deterministic tests
import random, numpy as np
random.seed(42)
np.random.seed(42)

from app.market.simulator import GBMSimulator

sim = GBMSimulator(tickers=["AAPL"], event_probability=0.0)
result = sim.step()
assert "AAPL" in result
assert result["AAPL"] > 0
```

### Testing SimulatorDataSource Lifecycle

```python
import asyncio
from app.market import PriceCache
from app.market.simulator import SimulatorDataSource

async def test_simulator_lifecycle():
    cache = PriceCache()
    source = SimulatorDataSource(cache, update_interval=0.1)

    await source.start(["AAPL", "GOOGL"])
    assert "AAPL" in cache     # Seeded immediately
    assert "GOOGL" in cache

    await asyncio.sleep(0.2)   # Let it run a couple of steps
    assert cache.version >= 2  # At least one step completed

    await source.add_ticker("MSFT")
    assert "MSFT" in cache     # Seeded immediately on add

    await source.stop()
    # Task is cancelled; cache retains last known prices
```

### Testing MassiveDataSource with Mocks

```python
from unittest.mock import MagicMock, patch, AsyncMock
from app.market import PriceCache
from app.market.massive_client import MassiveDataSource

async def test_massive_poll_updates_cache():
    cache = PriceCache()
    source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60)
    source._client = MagicMock()  # Inject mock client

    # Build a fake snapshot
    snap = MagicMock()
    snap.ticker = "AAPL"
    snap.last_trade.price = 195.00
    snap.last_trade.timestamp = 1736940645000  # ms

    source._client.get_snapshot_all.return_value = [snap]

    # Replace _fetch_snapshots to call the mock client synchronously
    source._fetch_snapshots = lambda: source._client.get_snapshot_all(
        market_type=..., tickers=source._tickers
    )

    await source._poll_once()
    assert cache.get_price("AAPL") == 195.00
```

### Demo Script

A Rich terminal dashboard demo is included:

```bash
cd backend
uv run market_data_demo.py
```

Shows a live-updating table of all 10 tickers with prices, sparklines, and an event log. Runs for 60 seconds (or until Ctrl+C). Useful for visual confirmation that the simulator is working.

---

## Summary: Key Contracts for Downstream Code

| Need | What to call | Module |
|---|---|---|
| Get price for one ticker | `cache.get_price("AAPL")` | `app.market.cache` |
| Get full PriceUpdate (direction, change) | `cache.get("AAPL")` | `app.market.cache` |
| Get all prices at once | `cache.get_all()` | `app.market.cache` |
| Add ticker (user adds to watchlist) | `await market_source.add_ticker("TSLA")` | via `MarketDataSource` |
| Remove ticker (user removes from watchlist) | `await market_source.remove_ticker("GOOGL")` | via `MarketDataSource` |
| Initialize everything (app startup) | `source = create_market_data_source(cache); await source.start(tickers)` | `app.market.factory` |
| Shutdown (app shutdown) | `await market_source.stop()` | via `MarketDataSource` |
| Mount SSE endpoint | `app.include_router(create_stream_router(cache))` | `app.market.stream` |
