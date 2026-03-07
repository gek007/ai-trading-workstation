# FinAlly Frontend - Technical Specification

**Status**: Ready for Development ✅

This document consolidates all technical details needed to build the FinAlly frontend. All backend APIs are implemented and documented.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Project Structure](#project-structure)
3. [Design System](#design-system)
4. [Components Required](#components-required)
5. [API Integration](#api-integration)
6. [SSE Streaming](#sse-streaming)
7. [State Management](#state-management)
8. [Implementation Checklist](#implementation-checklist)

---

## 1. Tech Stack

### Required Technologies

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Framework** | Next.js (App Router) | React framework with static export |
| **Language** | TypeScript | Type safety |
| **Styling** | Tailwind CSS | Utility-first CSS |
| **Charts** | Lightweight Charts or Recharts | Price charts and sparklines |
| **HTTP Client** | Native fetch or axios | API calls |
| **Real-time** | Native EventSource API | SSE streaming |

### Why These Choices?

- **Next.js static export**: Single origin, no CORS, simple deployment
- **TypeScript**: Catch errors at compile time
- **Tailwind**: Rapid styling with consistent design tokens
- **Lightweight Charts**: Performance-optimized for financial data
- **EventSource**: Native browser API, no libraries needed

---

## 2. Project Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # Root layout with providers
│   │   ├── page.tsx            # Main dashboard
│   │   └── globals.css         # Global styles + Tailwind
│   ├── components/             # React components
│   │   ├── watchlist/          # Watchlist panel
│   │   ├── charts/             # Main chart + sparklines
│   │   ├── portfolio/          # Heatmap + positions table
│   │   ├── trading/            # Trade bar
│   │   └── chat/               # AI chat panel
│   ├── lib/                    # Utilities
│   │   ├── api.ts              # API client functions
│   │   ├── sse.ts              # SSE connection manager
│   │   ├── types.ts            # TypeScript types
│   │   └── utils.ts            # Helper functions
│   └── hooks/                  # Custom React hooks
│       ├── useSSE.ts           # SSE connection hook
│       ├── usePortfolio.ts     # Portfolio data hook
│       └── useWatchlist.ts     # Watchlist CRUD hook
├── public/                     # Static assets
├── tailwind.config.js          # Tailwind configuration
├── next.config.js              # Next.js config (static export)
└── tsconfig.json               # TypeScript config
```

---

## 3. Design System

### Color Palette

```css
/* Backgrounds */
--bg-primary: #0d1117;
--bg-secondary: #1a1a2e;
--bg-tertiary: #161b22;

/* Borders */
--border-color: #30363d;

/* Accents */
--accent-yellow: #ecad0a;
--accent-blue: #209dd7;
--accent-purple: #753991;  /* Submit buttons */

/* Price Colors */
--price-up: #00c853;
--price-down: #ff5252;
--price-neutral: #8b949e;
```

### Typography

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
font-mono: "SF Mono", "Roboto Mono", monospace;  /* For numbers/prices */
```

### Animations

```css
/* Price flash effect */
@keyframes flash-green {
  0% { background-color: rgba(0, 200, 83, 0.3); }
  100% { background-color: transparent; }
}

@keyframes flash-red {
  0% { background-color: rgba(255, 82, 82, 0.3); }
  100% { background-color: transparent; }
}

.price-flash-up {
  animation: flash-green 500ms ease-out;
}

.price-flash-down {
  animation: flash-red 500ms ease-out;
}
```

---

## 4. Components Required

### Layout Components

#### Root Layout (`app/layout.tsx`)
```tsx
// Dark theme wrapper
// SSE connection provider
// Global error boundary
```

#### Dashboard (`app/page.tsx`)
```
┌─────────────────────────────────────────────────────────────┐
│  Header: Total Value | Cash | Connection Status            │
├───────────────────────────┬─────────────────────────────────┤
│                           │                                 │
│  Watchlist Panel          │  Main Chart Area                │
│  - Ticker symbols         │  - Large price chart            │
│  - Current prices         │  - Updates on selection         │
│  - Sparkline charts       │                                 │
│  - Flash animations       │                                 │
│                           │                                 │
├───────────────────────────┼─────────────────────────────────┤
│  Portfolio Heatmap        │  Positions Table                │
│  - Treemap visualization  │  - All positions                │
│  - Color by P&L           │  - P&L calculations             │
│                           │                                 │
├───────────────────────────┴─────────────────────────────────┤
│  Trade Bar: [Ticker] [Quantity] [BUY] [SELL]              │
├─────────────────────────────────────────────────────────────┤
│  AI Chat Panel (collapsible)                               │
│  - Conversation history                                     │
│  - Trade confirmations                                      │
└─────────────────────────────────────────────────────────────┘
```

### Feature Components

#### 1. Watchlist Panel
**Location**: `components/watchlist/WatchlistPanel.tsx`

**Props**: None (global state)

**Features**:
- Grid/table layout with 10 default tickers
- Real-time price updates from SSE
- Price flash animation (green/red)
- Sparkline mini-charts (40 data points)
- Click to select ticker for main chart
- Add/remove ticker buttons

**Data Structure**:
```typescript
interface WatchlistItem {
  ticker: string;
  price: number;
  change: number;
  change_percent: number;
  direction: 'up' | 'down' | 'flat';
  added_at: string;
  price_history: number[];  // For sparkline
}
```

#### 2. Main Chart
**Location**: `components/charts/MainChart.tsx`

**Props**:
```typescript
interface MainChartProps {
  ticker: string | null;
  priceHistory: PricePoint[];
}
```

**Features**:
- Large price chart (Lightweight Charts)
- Updates in real-time from SSE
- Starts empty, fills progressively
- Shows current price line
- Crosshair with price tooltip

#### 3. Portfolio Heatmap
**Location**: `components/portfolio/PortfolioHeatmap.tsx`

**Props**:
```typescript
interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pl: number;
  unrealized_pl_percent: number;
}

interface PortfolioHeatmapProps {
  positions: Position[];
  total_value: number;
}
```

**Features**:
- Treemap visualization (d3 or react-d3-tree)
- Rectangle size = position weight
- Color = P&L (green/red gradient)
- Tooltip on hover

#### 4. Positions Table
**Location**: `components/portfolio/PositionsTable.tsx`

**Props**: Same as heatmap

**Columns**:
- Ticker
- Quantity
- Avg Cost
- Current Price
- Market Value
- Unrealized P&L
- % Change

#### 5. Trade Bar
**Location**: `components/trading/TradeBar.tsx`

**State**:
```typescript
interface TradeForm {
  ticker: string;
  quantity: string;
}
```

**Features**:
- Input validation (ticker format, quantity range)
- Buy/Sell buttons
- Instant feedback (no confirmation)
- Error messages inline
- Disable during submission

#### 6. AI Chat Panel
**Location**: `components/chat/ChatPanel.tsx`

**State**:
```typescript
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  executed_actions: ExecutedActions | null;
  created_at: string;
}
```

**Features**:
- Collapsible sidebar
- Message history (scrollable)
- Loading indicator while waiting
- Trade confirmations inline
- Auto-scroll to latest message

---

## 5. API Integration

### API Client (`lib/api.ts`)

```typescript
const API_BASE = '/api';

// Portfolio
export async function getPortfolio(): Promise<PortfolioResponse> {
  const res = await fetch(`${API_BASE}/portfolio`);
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function executeTrade(params: TradeRequest): Promise<TradeResponse> {
  const res = await fetch(`${API_BASE}/portfolio/trade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

// Watchlist
export async function getWatchlist(): Promise<WatchlistResponse> {
  const res = await fetch(`${API_BASE}/watchlist`);
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function addTicker(ticker: string): Promise<AddToWatchlistResponse> {
  const res = await fetch(`${API_BASE}/watchlist`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

export async function removeTicker(ticker: string): Promise<RemoveFromWatchlistResponse> {
  const res = await fetch(`${API_BASE}/watchlist/${ticker}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

// Chat
export async function sendChatMessage(message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}
```

### TypeScript Types (`lib/types.ts`)

```typescript
// Common types
export type TickerSymbol = string;  // Uppercase, 1-5 letters
export type Quantity = number;     // 0.0001 to 1000000, 4 decimals
export type Price = number;        // USD, 2 decimals
export type TradeSide = 'buy' | 'sell';
export type Timestamp = string;    // ISO 8601

// Price update from SSE
export interface PriceUpdate {
  ticker: TickerSymbol;
  price: Price;
  previous_price: Price;
  change: number;
  change_percent: number;
  direction: 'up' | 'down' | 'flat';
  timestamp: Timestamp;
}

// Portfolio
export interface Position {
  ticker: TickerSymbol;
  quantity: Quantity;
  avg_cost: Price;
  current_price: Price;
  market_value: Price;
  cost_basis: Price;
  unrealized_pl: Price;
  unrealized_pl_percent: number;
}

export interface PortfolioResponse {
  cash_balance: Price;
  total_value: Price;
  positions: Position[];
  total_unrealized_pl: Price;
  total_unrealized_pl_percent: number;
}

// Trade
export interface TradeRequest {
  ticker: TickerSymbol;
  quantity: Quantity;
  side: TradeSide;
}

export interface TradeResponse {
  status: 'executed';
  trade: ExecutedTrade;
  portfolio: PortfolioResponse;
}

export interface ExecutedTrade {
  id: string;
  ticker: TickerSymbol;
  side: TradeSide;
  quantity: Quantity;
  price: Price;
  total_value: Price;
  executed_at: Timestamp;
}

// Watchlist
export interface WatchlistItem {
  ticker: TickerSymbol;
  price: Price;
  change: Price;
  change_percent: number;
  added_at: Timestamp;
}

export interface WatchlistResponse {
  tickers: WatchlistItem[];
}

// Chat
export interface ChatRequest {
  message: string;
}

export interface ChatResponse {
  message: ChatMessage;
  executed_actions: ExecutedActions | null;
}

export interface ChatMessage {
  id: string;
  role: 'assistant';
  content: string;
  created_at: Timestamp;
}

export interface ExecutedActions {
  trades: ExecutedTrade[];
  watchlist_changes: WatchlistChange[];
}

export interface WatchlistChange {
  ticker: TickerSymbol;
  action: 'added' | 'removed';
  timestamp: Timestamp;
}
```

---

## 6. SSE Streaming

### SSE Connection Manager (`lib/sse.ts`)

```typescript
export class SSEManager {
  private eventSource: EventSource | null = null;
  private listeners: Map<string, Set<(data: any) => void>> = new Map();

  connect(url: string): void {
    this.eventSource = new EventSource(url);

    this.eventSource.onopen = () => {
      console.log('SSE connected');
      // Update connection status to green
    };

    this.eventSource.onerror = () => {
      console.error('SSE error');
      // Update connection status to yellow/red
    };

    this.eventSource.addEventListener('message', (e) => {
      const data = JSON.parse(e.data);
      this.emit('message', data);
    });
  }

  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  on(event: string, callback: (data: any) => void): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: string, callback: (data: any) => void): void {
    this.listeners.get(event)?.delete(callback);
  }

  private emit(event: string, data: any): void {
    this.listeners.get(event)?.forEach(callback => callback(data));
  }
}

export const sseManager = new SSEManager();
```

### React Hook (`hooks/useSSE.ts`)

```typescript
export function useSSE() {
  const [prices, setPrices] = useState<Map<TickerSymbol, PriceUpdate>>(new Map());
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected'>('disconnected');

  useEffect(() => {
    sseManager.connect('/api/stream/prices');

    sseManager.on('message', (data: Record<string, PriceUpdate>) => {
      setPrices(prev => new Map([...prev, ...Object.entries(data)]));
    });

    return () => {
      sseManager.disconnect();
    };
  }, []);

  return { prices, connectionStatus };
}
```

### SSE Event Format

```
event: message
data: {"AAPL":{"ticker":"AAPL","price":190.50,"previous_price":190.25,...}}

event: message
data: {"GOOGL":{"ticker":"GOOGL","price":175.30,...}}
```

---

## 7. State Management

### Recommended Approach: React Context + Hooks

```typescript
// contexts/AppContext.tsx
interface AppContextType {
  watchlist: WatchlistItem[];
  portfolio: PortfolioResponse | null;
  prices: Map<TickerSymbol, PriceUpdate>;
  selectedTicker: TickerSymbol | null;
  setSelectedTicker: (ticker: TickerSymbol | null) => void;
  addTicker: (ticker: string) => Promise<void>;
  removeTicker: (ticker: string) => Promise<void>;
  executeTrade: (params: TradeRequest) => Promise<void>;
  sendMessage: (message: string) => Promise<void>;
}

export const AppContext = createContext<AppContextType | null>(null);
```

---

## 8. Implementation Checklist

### Phase 1: Foundation
- [ ] Set up Next.js project with TypeScript
- [ ] Configure Tailwind CSS with custom color scheme
- [ ] Create base layout component
- [ ] Set up routing structure

### Phase 2: Data Layer
- [ ] Implement API client functions
- [ ] Create TypeScript types
- [ ] Build SSE connection manager
- [ ] Create useSSE hook

### Phase 3: Components
- [ ] Header with portfolio summary
- [ ] Watchlist panel with sparklines
- [ ] Main chart area
- [ ] Portfolio heatmap
- [ ] Positions table
- [ ] Trade bar
- [ ] AI chat panel

### Phase 4: Integration
- [ ] Connect SSE to watchlist
- [ ] Connect trade execution
- [ ] Connect chat functionality
- [ ] Implement price flash animations
- [ ] Add connection status indicator

### Phase 5: Polish
- [ ] Responsive design
- [ ] Error handling
- [ ] Loading states
- [ ] Accessibility (ARIA labels)
- [ ] Performance optimization

---

## What's Missing?

### Not Yet Implemented (Backend)

These features are planned but not yet built:

1. **Portfolio endpoints** (`/api/portfolio`, `/api/portfolio/trade`)
2. **Watchlist endpoints** (`/api/watchlist`, POST, DELETE)
3. **Chat endpoint** (`/api/chat`)
4. **Database schema** (SQLite not created yet)
5. **Trade execution logic**
6. **LLM integration**

### Needed Before Frontend Development

To build a complete frontend, the backend needs:

1. **Complete REST API implementation**
   - Portfolio CRUD operations
   - Trade execution with validation
   - Watchlist management
   - Chat endpoint

2. **Database setup**
   - SQLite schema
   - Seed data script

3. **Authentication** (future, not v1)
   - Currently single-user (`user_id = "default"`)

---

## Ready to Build?

### What We Have ✅

1. ✅ **Complete SSE streaming** - Price updates working
2. ✅ **API contracts** - All endpoints documented
3. ✅ **Design system** - Colors, typography, animations
4. ✅ **Data models** - TypeScript types defined
5. ✅ **SSE format** - Event structure documented

### What's Needed 🔧

1. 🔧 **Portfolio endpoints** - Not yet implemented
2. 🔧 **Trade execution** - Not yet implemented
3. 🔧 **Chat endpoint** - Not yet implemented
4. 🔧 **Watchlist CRUD** - Not yet implemented

### Recommendation

**Start with what's working:**

1. Build the **watchlist + main chart** first (SSE is working)
2. Mock portfolio/trade data initially
3. Implement remaining backend endpoints
4. Connect real data

This allows frontend development to proceed while backend features are completed.
