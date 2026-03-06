# Main Chart Data Source - RESOLVED ✅

**Critical Blocker #6 from Implementation Readiness Review - RESOLVED**

## Decision Made

Main chart uses **SSE accumulation** (same approach as sparklines).

## How It Works

### Data Source
- **No backend API endpoint** for historical chart data
- Main chart accumulates price data from SSE stream (`/api/stream/prices`) since page load
- Each ticker's price history is buffered client-side in an array
- When user clicks a ticker in watchlist, main chart displays that ticker's accumulated price history

### Architecture

```
SSE Stream (/api/stream/prices)
    ↓
Frontend receives price updates for ALL tickers every ~500ms
    ↓
Frontend buffers price history per ticker:
    ticker_prices = {
        "AAPL": [{price: 190.25, timestamp: "..."}, {price: 190.50, timestamp: "..."}, ...],
        "GOOGL": [{price: 175.30, timestamp: "..."}, {price: 175.40, timestamp: "..."}, ...],
        ...
    }
    ↓
User clicks ticker in watchlist
    ↓
Main chart renders that ticker's price history array
```

### Data Lifecycle

**On Page Load:**
- Price history arrays start empty
- SSE connection established
- Frontend begins buffering prices for all tickers in watchlist

**During Session:**
- Each SSE event adds new price points to arrays
- Arrays grow continuously (no pruning)
- Typical session (1 hour): ~7,200 data points per ticker (500ms interval)

**On Page Refresh:**
- All buffered data is lost (expected behavior)
- Price history arrays reset to empty
- Chart starts accumulating fresh data from reconnect

## Frontend Implementation

### Data Structure

```typescript
interface PricePoint {
  price: number;           // Current price (2 decimal places)
  timestamp: string;       // ISO timestamp
}

// Buffer of price history per ticker
type PriceHistoryBuffer = Record<TickerSymbol, PricePoint[]>;

// Example:
const priceHistory: PriceHistoryBuffer = {
  "AAPL": [
    { price: 190.25, timestamp: "2025-01-15T10:00:00.000Z" },
    { price: 190.50, timestamp: "2025-01-15T10:00:00.500Z" },
    { price: 190.75, timestamp: "2025-01-15T10:00:01.000Z" },
    // ... continues accumulating
  ],
  "GOOGL": [
    { price: 175.30, timestamp: "2025-01-15T10:00:00.000Z" },
    { price: 175.40, timestamp: "2025-01-15T10:00:00.500Z" },
    // ...
  ],
  // ... one entry per ticker in watchlist
};
```

### SSE Event Handling

```typescript
const eventSource = new EventSource('/api/stream/prices');

eventSource.addEventListener('price_update', (event) => {
  const data = JSON.parse(event.data);
  // data.tickers is an array of PriceUpdate objects

  // Buffer price for each ticker
  data.tickers.forEach((update) => {
    const { ticker, price, timestamp } = update;

    // Initialize array if first price for this ticker
    if (!priceHistory[ticker]) {
      priceHistory[ticker] = [];
    }

    // Append new price point
    priceHistory[ticker].push({
      price,
      timestamp
    });

    // Update watchlist display (flash animation, etc.)
    updateWatchlistDisplay(ticker, update);
  });
});
```

### Main Chart Display

```typescript
// When user clicks a ticker in watchlist
function selectTicker(ticker: TickerSymbol) {
  const history = priceHistory[ticker] || [];

  // Render chart with accumulated history
  renderMainChart({
    ticker,
    data: history,  // Array of {price, timestamp}
    // Chart will be empty on first load (no data accumulated yet)
    // Chart fills in progressively as SSE events arrive
  });
}

// Example using Lightweight Charts
function renderMainChart({ ticker, data }) {
  const candleSeries = chart.addCandlestickSeries();

  // Convert price points to candlestick format
  const candleData = data.map((point, index) => ({
    time: point.timestamp,
    open: point.price,   // Simplified: use price as open
    high: point.price,   // In real implementation, calculate OHLC
    low: point.price,
    close: point.price,
  }));

  candleSeries.setData(candleData);

  // Real-time updates
  eventSource.addEventListener('price_update', (event) => {
    const data = JSON.parse(event.data);
    const update = data.tickers.find(t => t.ticker === ticker);
    if (update) {
      candleSeries.update({
        time: update.timestamp,
        open: update.price,
        high: update.price,
        low: update.price,
        close: update.price,
      });
    }
  });
}
```

## User Experience

### First Launch (Empty Chart)
1. Page loads, watchlist appears
2. Main chart shows "No data yet - accumulating price history..."
3. As SSE events arrive, chart begins rendering
4. After ~5-10 seconds, meaningful chart data is visible

### During Session
1. User clicks different tickers in watchlist
2. Main chart immediately switches to show that ticker's accumulated history
3. Chart updates in real-time as new SSE events arrive (smooth animation)

### Page Refresh
1. All buffered price data is lost
2. Chart starts empty again
3. Data re-accumulates from SSE stream

### Edge Cases

**Ticker Added to Watchlist:**
- New ticker starts appearing in SSE events immediately
- Price history buffer initializes on first price event
- Chart shows data from that point forward (no historical data before addition)

**Ticker Removed from Watchlist:**
- Ticker stops appearing in SSE events
- Price history buffer is deleted (free memory)
- If user had this ticker selected, chart clears or selects default ticker

**No Data Yet (First 5 seconds):**
- Chart shows loading state: "Accumulating price data..."
- Or shows empty chart with message: "Waiting for price updates..."

**SSE Disconnection:**
- Chart stops updating
- Show connection status indicator (yellow/red)
- On reconnect, continue buffering (gap in data is acceptable)

## Sparklines vs Main Chart

| Feature | Sparkline | Main Chart |
|---------|-----------|------------|
| **Data source** | SSE accumulation | SSE accumulation |
| **Data retention** | Since page load | Since page load |
| **Lost on refresh** | Yes | Yes |
| **Number of tickers** | All in watchlist (10) | One selected ticker |
| **Chart type** | Line/area | Candlestick/line |
| **Detail level** | Mini, simplified | Larger, detailed |
| **Interactivity** | Click to select main chart | Zoom, pan, hover details |
| **Time range** | Since page load | Since page load |

**Key Difference:** Both use same data source and accumulation strategy. Main chart is just a larger, more interactive view of the same data.

## Backend Implications

### No Changes Required
- ✅ No new API endpoints needed
- ✅ No historical price storage needed
- ✅ No complex queries or aggregations
- ✅ SSE endpoint already specified in API contracts

### What Backend Does Provide
- ✅ SSE stream at `/api/stream/prices` (already specified)
- ✅ Real-time price updates every ~500ms
- ✅ All tickers in watchlist in each event

## Benefits

1. **Simpler Backend** - No need to store historical intraday prices
2. **Consistent Architecture** - Both sparklines and main chart use SSE accumulation
3. **Real-time Experience** - Chart updates live with price movements
4. **Scalable** - No database load for historical queries
5. **Efficient** - Client-side buffering is lightweight

## Trade-offs

### Acceptable Limitations
- **No historical data on refresh** - Chart starts empty (consistent with sparklines)
- **Session-limited history** - Only shows data since page load (by design)
- **Data loss on disconnect** - Gaps in chart if SSE reconnects (acceptable for demo)

### Why This Is OK
- It's a **demo/trading simulator**, not production trading platform
- Main use case is **live monitoring**, not historical analysis
- User can see **real-time price action** which is the primary value
- Simplicity outweighs historical persistence for v1

## Future Enhancements (Phase 2)

If historical chart data is needed later:
1. Add backend endpoint: `GET /api/chart/{ticker}?period=1d`
2. Store intraday price snapshots (e.g., 1-minute candles)
3. On page load, fetch historical data from API
4. Then continue accumulating via SSE
5. Merge historical + live data for seamless chart

**For v1:** Keep it simple - SSE accumulation only.

## Specification Updates Needed

### Update PLAN.md Section 10 (Frontend Design)

**Current (line 356):**
> - **Main chart area** — larger chart for the currently selected ticker, with at minimum price over time. Clicking a ticker in the watchlist selects it here.

**Updated:**
> - **Main chart area** — larger chart for the currently selected ticker, displaying price history accumulated from SSE since page load. Chart updates in real-time as new price events arrive. Clicking a ticker in the watchlist selects it here. Chart starts empty on page load and fills progressively as data accumulates.

### Add to API_CONTRACTS.md

Add note clarifying that no chart data endpoint exists:

```
## Chart Data

**Note:** There is no backend API endpoint for historical chart data. The main chart
accumulates price history client-side from the SSE stream (`/api/stream/prices`).

Each ticker's price history is buffered in memory since page load. When a user clicks
a ticker in the watchlist, the main chart renders that ticker's accumulated price
history. Data is ephemeral and resets on page refresh.

This approach is consistent with sparklines and simplifies the backend by eliminating
the need to store or query historical intraday prices.
```

## Files to Update

1. ✅ Created `planning/MAIN_CHART_DATA_SOURCE.md` (this document)
2. `planning/PLAN.md`:
   - Section 10: Frontend Design (line ~356)
   - Section 13: Review (mark Blocker #6 as resolved)
3. `planning/PLAN_IMPLEMENTATION_READINESS_REVIEW.md`:
   - Mark Blocker #6 as resolved
4. `planning/API_CONTRACTS.md`:
   - Add note about chart data source

## Status

✅ **CRITICAL BLOCKER #6 RESOLVED**

**Remaining Critical Blockers:** 1/7
1. ✅ API Contracts (RESOLVED)
2. ✅ Database Location (RESOLVED)
3. ✅ SSE Streaming Format (RESOLVED)
4. ✅ Trade Validation Rules (RESOLVED)
5. ✅ Fractional Share Precision (RESOLVED)
6. ✅ Main Chart Data Source (RESOLVED - this document)
7. ❌ Portfolio Snapshot Retention (still needed)

**Implementation Status:** Ready to begin! The only remaining blocker (#7) is for the portfolio snapshots feature, which can be simplified or deferred per the suggestions in Section 13.

All core features (trading, portfolio tracking, AI chat, watchlist, price streaming, main chart) are now fully specified and ready for implementation.
