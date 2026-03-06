# FinAlly API Contracts

Complete request/response schemas for all FinAlly API endpoints. This document serves as the single source of truth for API contracts between frontend and backend.

## Table of Contents

1. [Common Types](#common-types)
2. [Error Responses](#error-responses)
3. [Market Data Endpoints](#1-market-data)
4. [Portfolio Endpoints](#2-portfolio)
5. [Watchlist Endpoints](#3-watchlist)
6. [Chat Endpoints](#4-chat)
7. [System Endpoints](#5-system)

---

## Common Types

### Ticker Symbol
```typescript
type TickerSymbol = string;  // Uppercase, 1-5 characters, letters only
// Examples: "AAPL", "GOOGL", "MSFT"
// Validation: /^[A-Z]{1,5}$/
```

### Quantity
```typescript
type Quantity = number;  // Fractional shares, 4 decimal places, positive
// Range: 0.0001 to 1000000
// Examples: 10, 1.5, 0.0001, 100.1234
// Stored as: integer (quantity * 10000) to avoid floating-point errors
```

### Price
```typescript
type Price = number;  // USD, 2 decimal places, positive
// Range: 0.01 to 10000000
// Examples: 190.50, 175.25, 1000.00
// Stored as: integer (price * 100) to avoid floating-point errors
```

### Trade Side
```typescript
type TradeSide = "buy" | "sell";
```

### Timestamp
```typescript
type Timestamp = string;  // ISO 8601 format, UTC timezone
// Example: "2025-01-15T10:30:45.123Z"
```

### UUID
```typescript
type UUID = string;  // Standard UUID v4 format
// Example: "550e8400-e29b-41d4-a716-446655440000"
```

---

## Error Responses

All error responses follow this standard format:

### Error Response Schema
```json
{
  "error": {
    "code": string,           // Machine-readable error code
    "message": string,        // Human-readable error message
    "details": object | null  // Additional error context (optional)
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Request body is invalid or missing required fields |
| `INVALID_TICKER` | 400 | Ticker symbol format is invalid |
| `INVALID_QUANTITY` | 400 | Quantity is outside valid range |
| `INVALID_SIDE` | 400 | Trade side must be "buy" or "sell" |
| `INSUFFICIENT_CASH` | 400 | Not enough cash to execute buy order |
| `INSUFFICIENT_SHARES` | 400 | Not enough shares to execute sell order |
| `TICKER_NOT_FOUND` | 404 | Ticker symbol not recognized |
| `WATCHLIST_NOT_FOUND` | 404 | Ticker not in user's watchlist |
| `WATCHLIST_EXISTS` | 409 | Ticker already in watchlist |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

### Error Response Examples

**Invalid Ticker Format:**
```json
{
  "error": {
    "code": "INVALID_TICKER",
    "message": "Ticker symbol must be 1-5 uppercase letters",
    "details": {
      "ticker": "aapl1",
      "pattern": "^[A-Z]{1,5}$"
    }
  }
}
```

**Insufficient Cash:**
```json
{
  "error": {
    "code": "INSUFFICIENT_CASH",
    "message": "Cannot buy 10 shares of AAPL at $190.50: insufficient cash (have $1,000.00, need $1,905.00)",
    "details": {
      "ticker": "AAPL",
      "quantity": 10,
      "price": 190.50,
      "required": 1905.00,
      "available": 1000.00
    }
  }
}
```

**Insufficient Shares:**
```json
{
  "error": {
    "code": "INSUFFICIENT_SHARES",
    "message": "Cannot sell 50 shares of AAPL: only 25.5000 shares owned",
    "details": {
      "ticker": "AAPL",
      "requested": 50,
      "owned": 25.5
    }
  }
}
```

---

## 1. Market Data

### 1.1 Stream Price Updates (SSE)

**Endpoint:** `GET /api/stream/prices`

**Description:** Server-Sent Events stream of live price updates for all tickers in the user's watchlist.

**Format:** Single SSE event containing array of all ticker prices (pushed every ~500ms)

**Event Schema:**
```typescript
interface PriceUpdateEvent {
  tickers: PriceUpdate[];
}

interface PriceUpdate {
  ticker: TickerSymbol;    // Ticker symbol
  price: Price;            // Current price (2 decimal places)
  previous_price: Price;   // Previous price (for change calculation)
  change: number;          // Price change (price - previous_price, 2 decimal places)
  change_percent: number;  // Change as percentage (2 decimal places)
  direction: "up" | "down" | "unchanged";  // Price movement direction
  timestamp: Timestamp;    // When this price was recorded
}
```

**SSE Event Format:**
```
event: price_update
data: {"tickers":[
  {"ticker":"AAPL","price":190.50,"previous_price":190.25,"change":0.25,"change_percent":0.13,"direction":"up","timestamp":"2025-01-15T10:30:45.123Z"},
  {"ticker":"GOOGL","price":175.30,"previous_price":175.40,"change":-0.10,"change_percent":-0.06,"direction":"down","timestamp":"2025-01-15T10:30:45.123Z"},
  {"ticker":"MSFT","price":378.90,"previous_price":378.90,"change":0.00,"change_percent":0.00,"direction":"unchanged","timestamp":"2025-01-15T10:30:45.123Z"}
]}
```

**Client-Side Handling:**
```javascript
const eventSource = new EventSource('/api/stream/prices');

eventSource.addEventListener('price_update', (event) => {
  const data = JSON.parse(event.data);
  // data.tickers is an array of PriceUpdate objects
  console.log(`Received ${data.tickers.length} price updates`);
});
```

**Reconnection:** Automatic via EventSource built-in retry logic.

**No authentication required** (single-user mode).

---

## 2. Portfolio

### 2.1 Get Portfolio Summary

**Endpoint:** `GET /api/portfolio`

**Description:** Get current portfolio state including positions, cash balance, total value, and P&L.

**Request:** No body

**Response (200 OK):**
```typescript
interface PortfolioResponse {
  cash_balance: Price;           // Available cash (2 decimal places)
  total_value: Price;            // Total portfolio value (cash + positions)
  positions: Position[];         // Array of current positions
  total_unrealized_pl: Price;    // Total unrealized P&L across all positions
  total_unrealized_pl_percent: number;  // Total P&L as percentage
}

interface Position {
  ticker: TickerSymbol;          // Ticker symbol
  quantity: Quantity;            // Quantity owned (4 decimal places)
  avg_cost: Price;               // Average cost per share (2 decimal places)
  current_price: Price;          // Current market price (2 decimal places)
  market_value: Price;           // quantity * current_price (2 decimal places)
  cost_basis: Price;             // quantity * avg_cost (2 decimal places)
  unrealized_pl: Price;          // market_value - cost_basis (2 decimal places)
  unrealized_pl_percent: number; // unrealized_pl / cost_basis * 100 (2 decimal places)
}
```

**Example Response:**
```json
{
  "cash_balance": 5234.50,
  "total_value": 15234.50,
  "total_unrealized_pl": 234.50,
  "total_unrealized_pl_percent": 1.56,
  "positions": [
    {
      "ticker": "AAPL",
      "quantity": 10.5,
      "avg_cost": 185.00,
      "current_price": 190.50,
      "market_value": 2000.25,
      "cost_basis": 1942.50,
      "unrealized_pl": 57.75,
      "unrealized_pl_percent": 2.97
    },
    {
      "ticker": "GOOGL",
      "quantity": 5.25,
      "avg_cost": 172.00,
      "current_price": 175.30,
      "market_value": 920.33,
      "cost_basis": 903.00,
      "unrealized_pl": 17.33,
      "unrealized_pl_percent": 1.92
    }
  ]
}
```

**Error Responses:**
- `500 INTERNAL_ERROR`: Database query failed

---

### 2.2 Execute Trade

**Endpoint:** `POST /api/portfolio/trade`

**Description:** Execute a market order (buy or sell) with instant fill at current price.

**Request Body:**
```typescript
interface TradeRequest {
  ticker: TickerSymbol;    // Ticker to trade (uppercase, 1-5 letters)
  quantity: Quantity;      // Quantity to trade (0.0001 to 1000000, 4 decimal places)
  side: TradeSide;         // "buy" or "sell"
}
```

**Validation Rules:**
- `ticker`: Must match pattern `^[A-Z]{1,5}$`, must be in watchlist
- `quantity`: Must be >= 0.0001 and <= 1000000, max 4 decimal places
- `side`: Must be exactly "buy" or "sell"
- Buy orders: `quantity * current_price <= cash_balance`
- Sell orders: `quantity <= owned_quantity` for that ticker

**Example Request:**
```json
{
  "ticker": "AAPL",
  "quantity": 10.5,
  "side": "buy"
}
```

**Response (200 OK):**
```typescript
interface TradeResponse {
  status: "executed";      // Always "executed" for successful trades
  trade: ExecutedTrade;    // Details of executed trade
  portfolio: PortfolioResponse;  // Updated portfolio state
}

interface ExecutedTrade {
  id: UUID;                // Trade ID
  ticker: TickerSymbol;    // Ticker symbol
  side: TradeSide;         // "buy" or "sell"
  quantity: Quantity;      // Quantity traded (4 decimal places)
  price: Price;            // Execution price (2 decimal places)
  total_value: Price;      // quantity * price (2 decimal places)
  executed_at: Timestamp;  // Execution timestamp
}
```

**Example Response:**
```json
{
  "status": "executed",
  "trade": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "ticker": "AAPL",
    "side": "buy",
    "quantity": 10.5,
    "price": 190.50,
    "total_value": 2000.25,
    "executed_at": "2025-01-15T10:30:45.123Z"
  },
  "portfolio": {
    "cash_balance": 3234.25,
    "total_value": 15234.50,
    "total_unrealized_pl": 234.50,
    "total_unrealized_pl_percent": 1.56,
    "positions": [...]
  }
}
```

**Error Responses:**
```json
// 400 INVALID_REQUEST
{"error":{"code":"INVALID_REQUEST","message":"Invalid request body","details":null}}

// 400 INVALID_TICKER
{"error":{"code":"INVALID_TICKER","message":"Ticker symbol must be 1-5 uppercase letters","details":{"ticker":"aapl1","pattern":"^[A-Z]{1,5}$"}}}

// 400 INVALID_QUANTITY
{"error":{"code":"INVALID_QUANTITY","message":"Quantity must be between 0.0001 and 1000000","details":{"quantity":0}}}

// 400 INVALID_SIDE
{"error":{"code":"INVALID_SIDE","message":"Side must be 'buy' or 'sell'","details":{"side":"hold"}}}

// 400 INSUFFICIENT_CASH
{"error":{"code":"INSUFFICIENT_CASH","message":"Cannot buy 10.5 shares of AAPL at $190.50: insufficient cash (have $1,000.00, need $2,000.25)","details":{"ticker":"AAPL","quantity":10.5,"price":190.50,"required":2000.25,"available":1000.00}}}

// 400 INSUFFICIENT_SHARES
{"error":{"code":"INSUFFICIENT_SHARES","message":"Cannot sell 50 shares of AAPL: only 10.5000 shares owned","details":{"ticker":"AAPL","requested":50,"owned":10.5}}}

// 404 TICKER_NOT_FOUND
{"error":{"code":"TICKER_NOT_FOUND","message":"Ticker 'XYZ' not found in watchlist. Add it to your watchlist first.","details":{"ticker":"XYZ"}}}
```

**Side Effects:**
- Creates entry in `trades` table
- Updates or creates entry in `positions` table
- Updates `cash_balance` in `users_profile` table

---

## 3. Watchlist

### 3.1 Get Watchlist

**Endpoint:** `GET /api/watchlist`

**Description:** Get current watchlist with latest prices.

**Request:** No body

**Response (200 OK):**
```typescript
interface WatchlistResponse {
  tickers: WatchlistItem[];
}

interface WatchlistItem {
  ticker: TickerSymbol;    // Ticker symbol
  price: Price;            // Current price (2 decimal places)
  change: Price;           // Price change from previous close (2 decimal places)
  change_percent: number;  // Change as percentage (2 decimal places)
  added_at: Timestamp;     // When ticker was added to watchlist
}
```

**Example Response:**
```json
{
  "tickers": [
    {
      "ticker": "AAPL",
      "price": 190.50,
      "change": 0.25,
      "change_percent": 0.13,
      "added_at": "2025-01-15T09:00:00.000Z"
    },
    {
      "ticker": "GOOGL",
      "price": 175.30,
      "change": -0.10,
      "change_percent": -0.06,
      "added_at": "2025-01-15T09:00:00.000Z"
    }
  ]
}
```

**Sorting:** Returned in order added to watchlist (oldest first).

**Error Responses:**
- `500 INTERNAL_ERROR`: Database query failed

---

### 3.2 Add Ticker to Watchlist

**Endpoint:** `POST /api/watchlist`

**Description:** Add a ticker to the user's watchlist.

**Request Body:**
```typescript
interface AddToWatchlistRequest {
  ticker: TickerSymbol;    // Ticker to add (uppercase, 1-5 letters)
}
```

**Validation Rules:**
- `ticker`: Must match pattern `^[A-Z]{1,5}$`
- Must not already be in watchlist

**Example Request:**
```json
{
  "ticker": "TSLA"
}
```

**Response (200 OK):**
```typescript
interface AddToWatchlistResponse {
  status: "added";              // Always "added" for successful adds
  ticker: TickerSymbol;         // Ticker that was added
  watchlist: WatchlistResponse; // Updated watchlist
}
```

**Example Response:**
```json
{
  "status": "added",
  "ticker": "TSLA",
  "watchlist": {
    "tickers": [
      {"ticker":"AAPL","price":190.50,"change":0.25,"change_percent":0.13,"added_at":"2025-01-15T09:00:00.000Z"},
      {"ticker":"GOOGL","price":175.30,"change":-0.10,"change_percent":-0.06,"added_at":"2025-01-15T09:00:00.000Z"},
      {"ticker":"TSLA","price":248.75,"change":2.50,"change_percent":1.02,"added_at":"2025-01-15T10:30:45.000Z"}
    ]
  }
}
```

**Error Responses:**
```json
// 400 INVALID_REQUEST
{"error":{"code":"INVALID_REQUEST","message":"Invalid request body","details":null}}

// 400 INVALID_TICKER
{"error":{"code":"INVALID_TICKER","message":"Ticker symbol must be 1-5 uppercase letters","details":{"ticker":"tsla1","pattern":"^[A-Z]{1,5}$"}}}

// 409 WATCHLIST_EXISTS
{"error":{"code":"WATCHLIST_EXISTS","message":"Ticker 'AAPL' is already in your watchlist","details":{"ticker":"AAPL"}}}
```

**Side Effects:**
- Creates entry in `watchlist` table
- Ticker immediately starts appearing in SSE price updates
- Simulator starts generating/streaming updates for this ticker

---

### 3.3 Remove Ticker from Watchlist

**Endpoint:** `DELETE /api/watchlist/{ticker}`

**Description:** Remove a ticker from the user's watchlist.

**URL Parameters:**
- `ticker`: Ticker symbol (case-insensitive, converted to uppercase)

**Request:** No body

**Response (200 OK):**
```typescript
interface RemoveFromWatchlistResponse {
  status: "removed";           // Always "removed" for successful removals
  ticker: TickerSymbol;        // Ticker that was removed
  watchlist: WatchlistResponse; // Updated watchlist
}
```

**Example Response:**
```json
{
  "status": "removed",
  "ticker": "TSLA",
  "watchlist": {
    "tickers": [
      {"ticker":"AAPL","price":190.50,"change":0.25,"change_percent":0.13,"added_at":"2025-01-15T09:00:00.000Z"},
      {"ticker":"GOOGL","price":175.30,"change":-0.10,"change_percent":-0.06,"added_at":"2025-01-15T09:00:00.000Z"}
    ]
  }
}
```

**Error Responses:**
```json
// 400 INVALID_TICKER
{"error":{"code":"INVALID_TICKER","message":"Ticker symbol must be 1-5 uppercase letters","details":{"ticker":"tsla1","pattern":"^[A-Z]{1,5}$"}}}

// 404 WATCHLIST_NOT_FOUND
{"error":{"code":"WATCHLIST_NOT_FOUND","message":"Ticker 'XYZ' is not in your watchlist","details":{"ticker":"XYZ"}}}
```

**Side Effects:**
- Deletes entry from `watchlist` table
- Ticker stops appearing in SSE price updates
- Simulator stops tracking this ticker for streaming updates
- **Note:** Positions in this ticker are NOT affected (user can still hold shares)

---

## 4. Chat

### 4.1 Send Chat Message

**Endpoint:** `POST /api/chat`

**Description:** Send a message to the AI trading assistant. The LLM may auto-execute trades or modify the watchlist.

**Request Body:**
```typescript
interface ChatRequest {
  message: string;  // User's message to the AI (1 to 1000 characters)
}
```

**Validation Rules:**
- `message`: Must be 1-1000 characters, trimmed

**Example Request:**
```json
{
  "message": "Buy 10 shares of AAPL"
}
```

**Response (200 OK):**
```typescript
interface ChatResponse {
  message: ChatMessage;        // Assistant's response message
  executed_actions: ExecutedActions | null;  // Actions auto-executed by LLM
}

interface ChatMessage {
  id: UUID;          // Message ID
  role: "assistant"; // Always "assistant" for responses
  content: string;   // Assistant's conversational response
  created_at: Timestamp;
}

interface ExecutedActions {
  trades: ExecutedTrade[];           // Trades that were executed
  watchlist_changes: WatchlistChange[];  // Watchlist modifications
}

interface ExecutedTrade {
  id: UUID;
  ticker: TickerSymbol;
  side: TradeSide;
  quantity: Quantity;
  price: Price;
  total_value: Price;
  executed_at: Timestamp;
}

interface WatchlistChange {
  ticker: TickerSymbol;
  action: "added" | "removed";
  timestamp: Timestamp;
}
```

**Example Response (with trades):**
```json
{
  "message": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "role": "assistant",
    "content": "I've bought 10 shares of AAPL at the current price of $190.50 for $1,905.00. Your portfolio now has 10 AAPL shares with an unrealized gain of $0.25.",
    "created_at": "2025-01-15T10:30:45.123Z"
  },
  "executed_actions": {
    "trades": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "ticker": "AAPL",
        "side": "buy",
        "quantity": 10,
        "price": 190.50,
        "total_value": 1905.00,
        "executed_at": "2025-01-15T10:30:45.000Z"
      }
    ],
    "watchlist_changes": []
  }
}
```

**Example Response (with watchlist change):**
```json
{
  "message": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "role": "assistant",
    "content": "I've added TSLA to your watchlist so we can monitor it. It's currently trading at $248.75, up 1.02% today.",
    "created_at": "2025-01-15T10:30:45.123Z"
  },
  "executed_actions": {
    "trades": [],
    "watchlist_changes": [
      {
        "ticker": "TSLA",
        "action": "added",
        "timestamp": "2025-01-15T10:30:45.000Z"
      }
    ]
  }
}
```

**Example Response (no actions):**
```json
{
  "message": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "role": "assistant",
    "content": "Your portfolio is well-diversified across 5 positions. Your best performer today is NVDA (+2.5%), and you have $3,234.25 in cash available for trading.",
    "created_at": "2025-01-15T10:30:45.123Z"
  },
  "executed_actions": null
}
```

**Example Response (trade failed):**
```json
{
  "message": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "role": "assistant",
    "content": "I attempted to buy 100 shares of AAPL at $190.50, but you only have $10,000.00 available and need $19,050.00. Would you like me to buy a smaller quantity?",
    "created_at": "2025-01-15T10:30:45.123Z"
  },
  "executed_actions": {
    "trades": [],
    "watchlist_changes": []
  }
}
```

**Error Responses:**
```json
// 400 INVALID_REQUEST
{"error":{"code":"INVALID_REQUEST","message":"Message is required and must be 1-1000 characters","details":null}}

// 500 INTERNAL_ERROR
{"error":{"code":"INTERNAL_ERROR","message":"Failed to process chat message","details":null}}
```

**Side Effects:**
- Creates entry in `chat_messages` table for user message
- Creates entry in `chat_messages` table for assistant response
- If trades executed: creates entries in `trades`, `positions`, updates `users_profile`
- If watchlist changes: creates/deletes entries in `watchlist` table

**LLM Context:**
- System prompt: "FinAlly, an AI trading assistant"
- Portfolio context: cash, positions with P&L, watchlist with live prices, total value
- Conversation history: last 20 messages from `chat_messages` table (user + assistant)
- User message: the new message from request body

**LLM Mock Mode (`LLM_MOCK=true`):**
Returns deterministic mock response:
```json
{
  "message": {
    "id": "mock-id-1",
    "role": "assistant",
    "content": "I've bought 10 shares of AAPL at the current price. (Mock response)",
    "created_at": "2025-01-15T10:30:45.123Z"
  },
  "executed_actions": {
    "trades": [
      {
        "id": "mock-trade-id",
        "ticker": "AAPL",
        "side": "buy",
        "quantity": 10,
        "price": 190.50,
        "total_value": 1905.00,
        "executed_at": "2025-01-15T10:30:45.000Z"
      }
    ],
    "watchlist_changes": []
  }
}
```

---

## 5. System

### 5.1 Health Check

**Endpoint:** `GET /api/health`

**Description:** Health check endpoint for Docker deployment and monitoring.

**Request:** No body

**Response (200 OK):**
```typescript
interface HealthResponse {
  status: "healthy";  // Always "healthy" if server is running
  version: string;    // Application version (e.g., "1.0.0")
  timestamp: Timestamp;
}
```

**Example Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-01-15T10:30:45.123Z"
}
```

**No authentication required.**

---

## Implementation Notes

### Decimal Precision Handling

**Backend (Python):**
- Store `quantity` as `INTEGER` (shares * 10000)
- Store `price` as `INTEGER` (dollars * 100)
- Convert to/from decimal for API responses

**Frontend (TypeScript):**
- Receive as `number` with 2-4 decimal places
- Display with `toFixed(2)` for prices, `toFixed(4)` for quantities
- Use decimal libraries for calculations if needed (e.g., `decimal.js`)

### Database Schema Mapping

**SQLite Types:**
- `TEXT` for: id, user_id, ticker, side, role, timestamps
- `INTEGER` for: quantity (internal representation), price (internal representation)
- `REAL` should be AVOIDED for money/quantities (floating-point errors)

### CORS Configuration

**Development:**
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Allow CORS for `http://localhost:3000`

**Production:**
- Same origin (no CORS needed)
- Static files served from `/`, API from `/api/*`

### Rate Limiting

**No rate limiting specified for v1.** Consider adding if abuse detected:
- Trade endpoint: 10 requests/minute
- Chat endpoint: 20 requests/minute
- Watchlist endpoints: 30 requests/minute

### Authentication

**No authentication for v1** (single-user mode). All endpoints use `user_id = "default"`.

### Pagination

**No pagination for v1:**
- `/api/watchlist`: Returns all tickers (typically 10-20 items)
- `/api/portfolio`: Returns all positions (typically 5-10 items)

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-15 | Initial API contracts specification |
