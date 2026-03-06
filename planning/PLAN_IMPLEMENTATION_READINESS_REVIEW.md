# PLAN.md Implementation Readiness Review

**Status**: ✅ **SUPERSEDED / RESOLVED** - This review is historical. Blockers were resolved in follow-up documents.

**Superseded by:**
- `planning/API_CONTRACTS.md`
- `planning/DATABASE_LOCATION_RESOLVED.md`
- `planning/MAIN_CHART_DATA_SOURCE.md`
- `planning/PORTFOLIO_SNAPSHOTS_REMOVED.md`
- `planning/IMPLEMENTATION_READY_SUMMARY.md`

---

## 🔴 CRITICAL BLOCKERS (Must Fix Before Starting)

These issues will stop implementation or cause significant rework if not clarified.

### 1. API Contract Specifications Missing
**Impact**: HIGH - Frontend and backend agents cannot work in parallel without this

The plan describes endpoints but provides **no request/response schemas**. This will cause:
- Frontend agent guessing at API shapes
- Backend agent guessing at response formats
- Integration failures when teams connect

**Missing for ALL endpoints**:
- Request body schema (JSON structure, required fields, types)
- Response body schema (success and error cases)
- HTTP status codes for each error scenario
- Validation rules and error message format

**Example - `/api/portfolio/trade` endpoint:**
```json
// MISSING: Request schema
{
  "ticker": "string (uppercase? length?)",
  "quantity": "number (min? max? precision?)",
  "side": "enum: ['buy', 'sell']"
}

// MISSING: Success response (200)
{
  "status": "executed",
  "trade": { ... },
  "updated_portfolio": { ... }
}

// MISSING: Error responses
// 400: Invalid input
// 400: Insufficient cash (buy)
// 400: Insufficient shares (sell)
// 404: Ticker not found
```

**Action Required**: Add "API Contracts" section with OpenAPI/Swagger specs for each endpoint.

---

### 2. Database Location Ambiguity
**Impact**: HIGH - Backend agent cannot initialize database correctly

The plan references **two different database locations**:
- Line 91: `backend/db/` - "Schema definitions, seed data, migration logic"
- Line 101: `db/` (root) - "Volume mount target (SQLite file lives here at runtime)"

**Questions that block implementation**:
1. Does the backend write to `backend/db/finally.db` or `db/finally.db`?
2. Which directory gets Docker volume mounted?
3. Where do schema SQL files live during development?
4. What's the path inside the container: `/app/backend/db` or `/app/db`?

**Decision Needed**: Choose ONE of these patterns:

**Option A - Schema in backend, runtime in root:**
```
finally/
├── backend/schema/          # SQL schema files (committed to git)
│   ├── schema.sql
│   └── seed.sql
├── db/                      # Runtime DB (gitignored, volume mounted)
│   └── finally.db
```

**Option B - Everything in backend:**
```
finally/
├── backend/db/              # Schema files + runtime DB
│   ├── schema.sql           # (committed)
│   ├── seed.sql             # (committed)
│   └── finally.db           # (gitignored, volume mounted)
```

**Action Required**: Update directory structure diagram and clarify in "Key Boundaries" section.

---

### 3. SSE Streaming Format Undefined
**Impact**: HIGH - Frontend cannot implement price streaming without this

Line 178 says: "Server pushes price updates for all tickers known to the system at a regular cadence (~500ms)"

**Critical ambiguity**:
- Is this **ONE SSE event** containing an array of all ticker prices?
- Or **MULTIPLE SSE events**, one per ticker?

**This changes frontend implementation completely**:

**Format A - Single event with array:**
```
event: price_update
data: {"tickers": [
  {"ticker": "AAPL", "price": 190.50, "prev": 190.25, "direction": "up", "timestamp": "..."},
  {"ticker": "GOOGL", "price": 175.30, "prev": 175.40, "direction": "down", "timestamp": "..."}
]}
```

**Format B - Individual events:**
```
event: price_update
data: {"ticker": "AAPL", "price": 190.50, "prev": 190.25, "direction": "up", "timestamp": "..."}

event: price_update
data: {"ticker": "GOOGL", "price": 175.30, "prev": 175.40, "direction": "down", "timestamp": "..."}
```

**Action Required**: Specify exact SSE event format with example.

---

### 4. Trade Validation Rules Undefined
**Impact**: MEDIUM - Backend cannot implement trade endpoint correctly

**Missing validation specifications**:
- **Minimum quantity**: Can user buy 0.00000001 shares? Or is there a minimum (e.g., 0.01 shares)?
- **Maximum quantity**: Any limit? (e.g., max 1,000,000 shares per trade)
- **Decimal precision**: How many decimal places for quantity? (2? 4? 6?)
- **Price precision**: How many decimal places for simulator prices? (2 for stocks, 4 for forex?)
- **Ticker validation**: Uppercase only? Max length? Valid characters (letters only, or numbers too)?
- **Negative quantities**: Explicitly rejected or implied by `side` field?
- **Zero quantity**: Is buying 0 shares an error or no-op?

**Current spec says**: "fractional shares supported" (lines 214, 224) - this is too vague.

**Action Required**: Add "Validation Rules" section with explicit rules.

---

### 5. Fractional Share Precision Unspecified
**Impact**: MEDIUM - Database schema and calculations depend on this

Lines 214, 224: `quantity REAL (fractional shares supported)`

**Problems**:
- SQLite `REAL` is floating-point - subject to precision errors
- For money/quantities, should use `DECIMAL` type or store as integer (cents/shares * 10^N)
- No guidance on decimal places for display

**Example precision issue**:
```python
# Floating point errors
0.1 + 0.2  # = 0.30000000000000004
1.0 - 0.9  # = 0.09999999999999998

# This breaks portfolio calculations:
# User buys 10.1 shares @ $100, sells 10.1 shares @ $100
# Expected: $0 P&L
# Actual: -$0.000000000000002 due to floating point
```

**Action Required**: Specify:
1. Decimal precision for quantities (e.g., "4 decimal places, stored as integer of shares * 10000")
2. Decimal precision for prices (e.g., "2 decimal places for stocks")
3. Display formatting rules

---

### 6. Main Chart Data Source Undefined
**Impact**: MEDIUM - Frontend cannot implement main chart

Line 356: "Clicking a ticker in the watchlist selects it here [main chart area], with at minimum price over time."

**Critical questions**:
- Where does the main chart get historical price data?
- Is there an API endpoint like `GET /api/chart/{ticker}?period=1d`?
- Or does frontend accumulate data from SSE (like sparklines)?
- What time ranges are available? (1 day? 1 week? 1 year?)
- What's the data resolution? (tick-by-tick? 1-minute candles? daily?)

**Current spec says sparklines are "accumulated from SSE since page load" (ephemeral), but main chart implies historical data.

**Action Required**: Add "Chart Data" section specifying data source and API endpoint (if any).

---

### 7. Portfolio Snapshot Data Retention Strategy Missing
**Impact**: MEDIUM - Will cause performance issues or data loss

Line 228: "Recorded every 30 seconds by a background task"

**Problem**: Unbounded data growth
- 2,880 snapshots/day
- 1,051,200 snapshots/year
- 10M+ snapshots over typical capstone project lifetime

**No specification for**:
- Retention policy (keep all? delete old? downsample?)
- Downsampling strategy (keep 30-second granularity for 7 days, then daily?)
- Cleanup mechanism (cron job? on-demand?)
- Maximum storage limit

**Action Required**: Specify retention policy or remove snapshot feature (see simplification suggestions).

---

## ⚠️ HIGH-PRIORITY GAPS (Should Fix)

These won't block implementation but will cause confusion, rework, or bugs.

### 8. Error Response Format Not Standardized
**Impact**: MEDIUM - Inconsistent error handling across endpoints

**No specification for**:
- Error response JSON schema
- Standard error codes
- Error message format (human-readable? machine-readable?)

**Example of what's needed**:
```json
// Standard error response
{
  "error": {
    "code": "INSUFFICIENT_CASH",
    "message": "Cannot buy 10 AAPL at $190.50: insufficient cash (have $1000.00, need $1905.00)",
    "details": {
      "required": 1905.00,
      "available": 1000.00
    }
  }
}
```

**Action Required**: Define error response schema in "API Contracts" section.

---

### 9. Conversation History Limit for LLM Context
**Impact**: MEDIUM - Will cause token limit errors or degraded LLM performance

Line 293: "Loads recent conversation history from the `chat_messages` table"

**Unspecified**:
- How many messages? (last 10? last 50? all?)
- Token limit? (e.g., max 4000 tokens of context)
- What happens when context is exceeded? (truncate old messages? error?)
- Does system prompt count against token limit?

**Problem**: If user chats for hours, conversation history will exceed LLM context window.

**Action Required**: Specify conversation history loading strategy.

---

### 10. Market Data Simulator Seed Prices Incomplete
**Impact**: MEDIUM - Simulator implementation will be incomplete

Line 156: "Starts from realistic seed prices (e.g., AAPL ~$190, GOOGL ~$175, etc.)"

**Problem**: Only 2 of 10 default tickers have seed prices specified.

**Missing seed prices for**:
- MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

**Also missing**:
- Drift parameter per ticker (expected return)
- Volatility parameter per ticker (risk)
- Correlation matrix (how tech stocks move together)
- Event probability (how often "drama" moves occur)

**Action Required**: Add seed price table and GBM parameters.

---

### 11. LLM Mock Response Schema Undefined
**Impact**: MEDIUM - Cannot implement E2E tests without this

Lines 342-345: "When `LLM_MOCK=true`, the backend returns deterministic mock responses"

**Unspecified**:
- What does the mock response look like?
- Does it always return the same response, or vary by input?
- Does it simulate different scenarios (successful trade, failed trade, watchlist change)?

**Example needed**:
```python
# LLM_MOCK=true response
{
  "message": "I'll buy 10 shares of AAPL for you at the current price.",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": []
}
```

**Action Required**: Specify mock response schema and scenarios.

---

### 12. Watchlist Update on SSE Not Specified
**Impact**: LOW - But affects user experience

**Scenario**: User adds ticker to watchlist via AI chat.

**Unspecified**:
- Does the new ticker immediately appear in SSE stream?
- Or does user need to refresh/reconnect?
- What happens if user adds invalid ticker?

**Action Required**: Specify watchlist update behavior in SSE section.

---

### 13. Sparkline vs Main Chart Data Inconsistency
**Impact**: LOW - But causes frontend implementation confusion

**Contradiction**:
- Sparklines: "accumulated from SSE since page load" (ephemeral, line 25)
- Main chart: "price over time" (implies historical data, line 356)

**Question**: If sparklines are ephemeral (lost on refresh), why doesn't main chart have same issue?

**Likely answer**: Main chart has backend data source, sparklines don't. But this isn't specified.

**Action Required**: Clarify data source for main chart vs sparklines.

---

## 📋 MISSING SPECIFICATIONS (Should Add)

### 14. No Pagination Specified
**Endpoints that could return large datasets**:
- `/api/portfolio/history` - thousands of snapshots
- `/api/watchlist` - could be hundreds of tickers

**Missing**: Pagination strategy (cursor? offset/limit? or no pagination?)

**Action Required**: Specify if pagination is needed, and if so, which strategy.

---

### 15. No Rate Limiting Specified
**Missing**: Rate limits on any endpoints?

**Scenarios to consider**:
- User spamming trade endpoint
- Bot adding thousands of watchlist items
- LLM making rapid API calls

**Action Required**: Specify if rate limiting is needed, and what limits.

---

### 16. No CORS Configuration
**Impact**: LOW - But affects development workflow

Line 369: "All API calls go to the same origin (`/api/*`) — no CORS configuration needed"

**Issue**: In development, frontend might run on `localhost:3000` while backend on `localhost:8000`. This requires CORS.

**Action Required**: Specify CORS configuration for development vs production.

---

### 17. No Database Connection Pooling
**Missing**: SQLite connection handling?

**Questions**:
- Single connection for all requests?
- Connection pooling?
- Per-request connection?

**Action Required**: Specify database connection strategy.

---

### 18. No Concurrent Request Handling
**Missing**: What happens if user submits multiple trades simultaneously?

**Scenarios**:
- User clicks "Buy" button twice quickly
- LLM executes trade while user also trades manually

**Action Required**: Specify if transactions/locking are needed.

---

### 19. No Timezone Handling
**Impact**: LOW - But causes timestamp confusion

**Unspecified**:
- What timezone are timestamps in? (UTC? local?)
- How does frontend display timestamps?

**Action Required**: Specify timezone for all timestamps.

---

### 20. No Input Sanitization
**Missing**: Security considerations

**Questions**:
- Are ticker symbols sanitized before database insertion?
- Are user messages sanitized before LLM context?
- SQL injection protection?

**Action Required**: Specify security practices.

---

## 🎯 RECOMMENDATIONS

### Before Starting Implementation:

1. **ADD API CONTRACTS SECTION** (Critical)
   - Request/response schemas for ALL endpoints
   - Error response format
   - Validation rules
   - HTTP status codes

2. **RESOLVE DATABASE LOCATION** (Critical)
   - Choose ONE location pattern
   - Update directory structure diagram
   - Document clearly in "Key Boundaries"

3. **SPECIFY SSE FORMAT** (Critical)
   - Exact event format with examples
   - Single vs multiple events

4. **DEFINE VALIDATION RULES** (Critical)
   - Trade quantity min/max/precision
   - Ticker format rules
   - Price precision

5. **ADD MAIN CHART SPEC** (Critical)
   - Data source (API endpoint or SSE accumulation)
   - Time ranges available
   - Data resolution

6. **SPECIFY SIMULATOR PARAMETERS** (High)
   - Seed prices for all tickers
   - GBM parameters (drift, volatility)
   - Correlation rules
   - Event probability

7. **DEFINE ERROR HANDLING** (High)
   - Standard error response schema
   - Error codes
   - User-facing error messages

8. **SPECIFY LLM CONTEXT STRATEGY** (High)
   - Conversation history limit
   - Token limit handling
   - Truncation strategy

### Consider Simplifying:

Per Section 13 simplification suggestions, consider:
- Remove `portfolio_snapshots` table (compute P&L from trades)
- Remove sparkline mini-charts (keep main chart only)
- Remove Massive API integration (ship simulator only)
- Defer portfolio heatmap (use color-coded table instead)

These simplifications eliminate blockers #7, #13, and reduce overall complexity.

---

## ✅ READINESS CHECKLIST (Historical)

This checklist has been completed via the superseding documents listed above.

- [x] API contracts section added with all request/response schemas
- [x] Database location decision made and documented
- [x] SSE streaming format specified with examples
- [x] Trade validation rules defined (quantity, ticker, price)
- [x] Main chart data source specified (API endpoint or SSE)
- [x] Simulator seed prices and parameters defined
- [x] Error response format standardized
- [x] LLM conversation history limit specified
- [x] LLM mock response schema defined
- [x] Portfolio snapshot retention policy specified

**Current Status**: 10/10 complete - **RESOLVED (see superseding docs)**

---

## 📊 SUMMARY

**Critical Blockers**: 7
**High-Priority Gaps**: 6
**Missing Specs**: 7

**Estimated Time to Address**: 2-3 hours of documentation work

**Risk of Starting Without Fixes**: HIGH - Will cause significant rework, integration failures, and agent confusion.

**Recommendation**: Address all Critical Blockers and at least 4 High-Priority Gaps before assigning implementation tasks to agents.
