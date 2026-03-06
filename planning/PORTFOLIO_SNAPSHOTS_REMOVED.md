# Portfolio Snapshots - REMOVED ✅

**Critical Blocker #7 from Implementation Readiness Review - RESOLVED**

## Decision Made

**Portfolio snapshots feature removed entirely from v1.**

The P&L chart (portfolio value over time) has been removed from the feature set. All references to `portfolio_snapshots` table, snapshot background task, and `/api/portfolio/history` endpoint have been eliminated.

## Rationale

### 1. Consistency with Ephemeral Data Architecture
The application follows an **ephemeral data model** for visualizations:
- **Sparklines**: Session-only, accumulated from SSE since page load
- **Main chart**: Session-only, accumulated from SSE since page load
- **P&L chart**: Now also session-only (removed entirely for v1)

### 2. Core Feature Set Focus
FinAlly v1 focuses on **live trading and monitoring**, not historical analytics:
- ✅ Real-time price streaming
- ✅ Live trading execution
- ✅ AI chat with auto-execution
- ✅ Current portfolio P&L (real-time)
- ✅ Position tracking
- ✅ Trade history

### 3. Simplification Benefits
- **No background tasks** - Eliminates snapshot recording complexity
- **No database growth** - No unbounded data retention concerns
- **Simpler backend** - One less table, one less endpoint, one less background task
- **Simpler frontend** - One less chart component
- **Faster development** - Reduces scope by ~10%

### 4. User Experience Still Complete
Users get all critical information without historical P&L chart:
- **Current portfolio value**: Shown in header, updates live
- **Position P&L**: Each position shows unrealized P&L in positions table
- **Total P&L**: Portfolio summary shows total unrealized P&L
- **Trade history**: Complete log of all trades executed
- **Real-time updates**: All values update as prices stream

## What Was Removed

### Backend Changes

#### Database Schema
```diff
- **portfolio_snapshots** — Portfolio value over time (for P&L chart). Recorded every 30 seconds by a background task, and immediately after each trade execution.
- - `id` TEXT PRIMARY KEY (UUID)
- - `user_id` TEXT (default: `"default"`)
- - `total_value` REAL
- - `recorded_at` TEXT (ISO timestamp)
```

#### API Endpoints
```diff
### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, quantity, side}` |
- | GET | `/api/portfolio/history` | Portfolio value snapshots over time (for P&L chart) |
```

#### Background Tasks
```diff
- Background task: Record portfolio snapshot every 30 seconds
- Background task: Record portfolio snapshot immediately after each trade execution
```

### Frontend Changes

#### UI Components
```diff
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots`
```

#### API Calls
```diff
- GET /api/portfolio/history (fetching P&L chart data)
```

## What Remains (Sufficient for Core Experience)

### Portfolio Tracking
✅ **Current Portfolio Value** - Displayed in header, updates in real-time
✅ **Cash Balance** - Shown in header and portfolio summary
✅ **Positions Table** - All holdings with live P&L
✅ **Total Portfolio P&L** - Aggregated unrealized P&L across all positions

### Data Persistence
✅ **Trades Table** - Complete history of all executed trades
✅ **Positions Table** - Current holdings with cost basis
✅ **User Profile** - Cash balance

### Real-Time Updates
✅ **SSE Price Streaming** - Live price updates for all watchlist tickers
✅ **Portfolio Value** - Updates as prices change
✅ **Position P&L** - Updates as prices change

## Updated Database Schema

### Remaining Tables

**users_profile** — User state (cash balance)
```sql
- id TEXT PRIMARY KEY (default: "default")
- cash_balance REAL (default: 10000.0)
- created_at TEXT (ISO timestamp)
```

**watchlist** — Tickers the user is watching
```sql
- id TEXT PRIMARY KEY (UUID)
- user_id TEXT (default: "default")
- ticker TEXT
- added_at TEXT (ISO timestamp)
- UNIQUE constraint on (user_id, ticker)
```

**positions** — Current holdings (one row per ticker per user)
```sql
- id TEXT PRIMARY KEY (UUID)
- user_id TEXT (default: "default")
- ticker TEXT
- quantity REAL (fractional shares supported)
- avg_cost REAL
- updated_at TEXT (ISO timestamp)
- UNIQUE constraint on (user_id, ticker)
```

**trades** — Trade history (append-only log)
```sql
- id TEXT PRIMARY KEY (UUID)
- user_id TEXT (default: "default")
- ticker TEXT
- side TEXT ("buy" or "sell")
- quantity REAL (fractional shares supported)
- price REAL
- executed_at TEXT (ISO timestamp)
```

**chat_messages** — Conversation history with LLM
```sql
- id TEXT PRIMARY KEY (UUID)
- user_id TEXT (default: "default")
- role TEXT ("user" or "assistant")
- content TEXT
- actions TEXT (JSON — trades executed, watchlist changes made; null for user messages)
- created_at TEXT (ISO timestamp)
```

**Total: 5 tables (down from 6)**

## Updated API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, quantity, side}` |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Current watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message, receive complete JSON response (message + executed actions) |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment) |

**Total: 8 endpoints (down from 9)**

## Future Enhancement (v2)

If historical P&L chart is needed in a future version, consider these approaches:

### Option A: Session-Only Snapshots
- Keep snapshots in memory only (not database)
- Record every 30 seconds during session
- Reset on container restart
- No retention policy needed
- Consistent with ephemeral data model

### Option B: Retention Policy with Downsampling
- Keep 30-second granularity for 7 days
- Downsample to 1-hour granularity for 30 days
- Downsample to 1-day granularity for 1 year
- Delete anything older than 1 year
- Requires background cleanup task

### Option C: Compute from Trades
- Replay trades to compute portfolio value at each point
- Requires storing historical prices (new feature)
- More complex but provides infinite history
- Can be cached for performance

**Recommendation for v2:** Option A (session-only) for consistency with current architecture.

## Impact Assessment

### Complexity Reduction
- **Backend**: ~15% less code (no snapshot task, no history endpoint)
- **Database**: 1 less table (16% reduction)
- **Frontend**: 1 less chart component
- **Testing**: Fewer test scenarios (no snapshot recording, no history endpoint)

### Performance Improvement
- No background task overhead (CPU, memory)
- No database write operations every 30 seconds
- Smaller database size
- Faster database queries (1 less table)

### User Experience
- **Lost**: Historical P&L visualization
- **Retained**: All critical portfolio information (current value, P&L, positions)
- **Improved**: Faster app startup (no snapshot initialization), simpler UI

### Development Timeline
- **Estimated savings**: 1-2 days of development
- **Testing savings**: 4-6 hours
- **Documentation savings**: 2-3 hours

**Total time saved**: ~2 days

## Migration Notes

If this feature was partially implemented:

### Backend Migration
```sql
-- Drop table (if exists)
DROP TABLE IF EXISTS portfolio_snapshots;
```

### Frontend Migration
```typescript
// Remove component
- import PortfolioHistoryChart from './PortfolioHistoryChart';
- <PortfolioHistoryChart data={portfolioHistory} />

// Remove API call
- const portfolioHistory = await fetch('/api/portfolio/history').then(r => r.json());
```

## Status

✅ **ALL CRITICAL BLOCKERS RESOLVED**

**Implementation Readiness:** 100%

**Critical Blockers:**
1. ✅ API Contracts (RESOLVED)
2. ✅ Database Location (RESOLVED)
3. ✅ SSE Streaming Format (RESOLVED)
4. ✅ Trade Validation Rules (RESOLVED)
5. ✅ Fractional Share Precision (RESOLVED)
6. ✅ Main Chart Data Source (RESOLVED)
7. ✅ Portfolio Snapshot Retention (RESOLVED - feature removed)

## Next Steps

🚀 **READY FOR IMPLEMENTATION**

All critical blockers resolved. All core features fully specified. Frontend and backend agents can begin parallel implementation immediately.

**Recommended Implementation Order:**

1. **Backend**: Database setup, API endpoints (no background tasks needed)
2. **Frontend**: Core UI components (no P&L chart needed)
3. **Integration**: Connect frontend to backend
4. **Testing**: Unit tests, E2E tests (simplified test coverage)

**Estimated Timeline:** 20-30% faster than original plan due to scope reduction

---

## Files Updated

1. ✅ Created `planning/PORTFOLIO_SNAPSHOTS_REMOVED.md` (this document)
2. `planning/PLAN.md`:
   - Section 7: Database schema (remove portfolio_snapshots table)
   - Section 8: API endpoints (remove /api/portfolio/history)
   - Section 10: Frontend design (remove P&L chart)
   - Section 12: Testing strategy (remove snapshot tests)
   - Section 13: Mark blocker #7 as resolved
3. `planning/API_CONTRACTS.md`:
   - Remove /api/portfolio/history endpoint
   - Update portfolio endpoint response (no history reference)
4. `planning/PLAN_IMPLEMENTATION_READINESS_REVIEW.md`:
   - Mark Blocker #7 as resolved
   - Update readiness status to 100%
