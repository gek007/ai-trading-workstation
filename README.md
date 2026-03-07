# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades via natural language.

Built entirely by coding agents as a capstone project for an agentic AI coding course, demonstrating how orchestrated AI agents can produce a production-quality full-stack application.

## What It Does

FinAlly provides a complete trading terminal experience:

- **Live Price Streaming** — Real-time market data via Server-Sent Events (SSE) with green/red flash animations on price changes
- **Portfolio Simulation** — Start with $10,000 virtual cash, trade market orders with instant fills, no fees
- **Interactive Charts** — Sparkline mini-charts in watchlist + detailed Lightweight Charts v5 area chart for the selected ticker
- **Portfolio Visualizations** — Squarified treemap heatmap (size = position weight, color = P&L) + positions table with unrealized P&L
- **AI Chat Assistant** — Natural language interface to analyze holdings, get suggestions, and auto-execute trades
- **Watchlist Management** — Add/remove tickers manually or via AI chat
- **Dark Terminal Aesthetic** — Bloomberg-inspired, data-dense layout optimized for desktop

## Architecture

Single-container, single-port architecture for simplicity:

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python / uv)                          │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving        │
│                      (Next.js export)           │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: GBM market data simulator     │
└─────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| **Frontend** | Next.js + TypeScript + Tailwind CSS | Next.js 16, React 19, Tailwind 4 |
| **Charts** | Lightweight Charts | v5.1 |
| **Backend** | FastAPI + uvicorn | FastAPI ≥0.115, Python 3.12+ |
| **Package manager** | uv | – |
| **Database** | SQLite (aiosqlite-less, sync) | – |
| **Real-time** | Server-Sent Events (SSE) | – |
| **AI** | LiteLLM → OpenRouter (Llama 3.3 70B) | LiteLLM ≥1.0 |
| **Market data** | GBM Simulator (default) / Massive API | – |

### Design Decisions

- **SSE over WebSockets** — One-way push is all we need; simpler implementation
- **SQLite over Postgres** — No auth/multi-user in v1; self-contained, zero setup
- **Market orders only** — Eliminates order book complexity; dramatically simpler
- **Auto-executing AI trades** — Simulated environment with fake money demonstrates agentic capabilities
- **Static export for production** — Next.js built to `backend/static/`; single port, zero CORS, simple deployment
- **Dev proxy rewrites** — During `npm run dev`, Next.js proxies `/api/*` to `localhost:8000` so both servers coexist

## Quick Start

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 20+
- OpenRouter API key ([get one here](https://openrouter.ai/))

### 1. Clone and configure

```bash
git clone <repo-url>
cd finally
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

### 2. Start the backend

```bash
cd backend
uv sync
uvicorn app.main:app --reload --port 8000
```

### 3. Start the frontend (development)

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

API calls from the dev server are automatically proxied to `localhost:8000`.

### 4. Production build (frontend served by backend)

```bash
cd frontend
npm run build      # outputs to frontend/out/
cp -r out/* ../backend/static/
```

Then open **http://localhost:8000**.

### Docker (single container)

```bash
# macOS/Linux
./scripts/start_mac.sh

# Windows (PowerShell)
.\scripts\start_windows.ps1
```

Open **http://localhost:8000**. The SQLite database persists via Docker volume.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes | — | OpenRouter API key for AI chat |
| `MASSIVE_API_KEY` | No | — | Massive (Polygon.io) key for real market data. Omit to use the built-in GBM simulator |
| `LLM_MOCK` | No | `false` | Set `true` for deterministic mock LLM responses (useful for testing) |
| `MARKET_SIM_SEED` | No | — | Seed for deterministic GBM price sequences |

## Project Structure

```
finally/
├── frontend/                   # Next.js TypeScript project
│   ├── app/
│   │   ├── globals.css         # Tailwind imports + design tokens
│   │   ├── layout.tsx          # Root layout (wraps AppProvider)
│   │   └── page.tsx            # Main dashboard grid
│   ├── components/
│   │   ├── Header.tsx          # Portfolio value, cash, connection status
│   │   ├── charts/
│   │   │   └── MainChart.tsx   # Lightweight Charts v5 area chart (SSR-safe)
│   │   ├── chat/
│   │   │   └── ChatPanel.tsx   # AI chat panel with action confirmations
│   │   ├── portfolio/
│   │   │   ├── PortfolioHeatmap.tsx  # SVG squarified treemap
│   │   │   └── PositionsTable.tsx    # Positions with unrealized P&L
│   │   ├── trading/
│   │   │   └── TradeBar.tsx    # Buy/sell order entry form
│   │   └── watchlist/
│   │       ├── Sparkline.tsx   # SVG mini price chart
│   │       └── WatchlistPanel.tsx    # Watchlist with price flash animations
│   ├── contexts/
│   │   └── AppContext.tsx      # Global state (prices, portfolio, watchlist, chat)
│   ├── hooks/
│   │   └── useSSE.ts           # EventSource hook with reconnect + price history
│   ├── lib/
│   │   ├── api.ts              # Typed fetch wrappers for all REST endpoints
│   │   ├── types.ts            # TypeScript interfaces (API + UI models)
│   │   └── utils.ts            # Price/percentage formatters, P&L CSS helpers
│   ├── next.config.ts          # Static export (prod) + dev proxy rewrites
│   └── package.json
│
├── backend/                    # FastAPI uv project
│   ├── app/
│   │   ├── main.py             # FastAPI app, lifespan, CORS, static files
│   │   ├── chat/               # LLM integration (LiteLLM → OpenRouter)
│   │   ├── db/                 # Schema init + seed data
│   │   ├── market/             # GBM simulator, Massive client, SSE stream, price cache
│   │   ├── portfolio/          # Trade execution, P&L calculation
│   │   └── watchlist/          # Watchlist CRUD with live price injection
│   ├── db/
│   │   └── finally.db          # Runtime SQLite DB (gitignored, volume-mounted)
│   ├── static/                 # Next.js static export (copied from frontend/out/)
│   └── pyproject.toml
│
├── planning/                   # Project documentation for agents
│   ├── PLAN.md                 # Canonical v1 scope specification
│   ├── API_CONTRACTS.md        # API schemas, SSE wire format
│   └── FRONTEND_SPEC.md        # Frontend design system + component spec
│
├── test/                       # Playwright E2E tests
├── scripts/                    # Docker start/stop scripts
├── Dockerfile                  # Multi-stage build (Node → Python)
├── docker-compose.yml
├── .env                        # Secrets (gitignored)
├── .env.example                # Template
└── README.md
```

## API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream — `event: price_update` with `{"tickers": [...]}` |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{"ticker", "quantity", "side"}` |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | All tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{"ticker"}` |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message; returns `{message, trades, watchlist_changes}` |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check: `{"status", "version", "timestamp"}` |

## SSE Wire Format

```
event: price_update
data: {"tickers": [{"ticker": "AAPL", "price": 191.42, "change": 0.34, "change_pct": 0.18, "direction": "up"}]}
```

`direction` is one of `"up"`, `"down"`, or `"unchanged"`.

## AI Chat

The LLM (Llama 3.3 70B via OpenRouter) responds with structured JSON:

```json
{
  "message": "Your conversational response",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

Trades and watchlist changes execute automatically and appear as inline confirmations in the chat panel.

## Database

SQLite with lazy initialization — created and seeded on first run.

| Table | Description |
|-------|-------------|
| `users_profile` | User state (cash balance) |
| `watchlist` | Watched tickers |
| `positions` | Current holdings |
| `trades` | Trade history (append-only log) |
| `chat_messages` | Conversation history |

**Seed data:** $10,000 starting cash · default watchlist: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

## Market Data

### GBM Simulator (default, no API key required)

- Geometric Brownian Motion with configurable drift/volatility
- Updates every ~500 ms
- Correlated moves across tickers (tech stocks move together)
- Occasional random "events" — sudden 2–5% moves for drama
- Realistic seed prices (AAPL ~$190, GOOGL ~$175, etc.)

### Real Data (optional)

Set `MASSIVE_API_KEY` to switch from the simulator to Massive (Polygon.io) polling.

## Development

### Running tests

```bash
cd backend
uv run pytest
```

### Linting

```bash
cd backend
uv run ruff check .
```

### Building the frontend for production

```bash
cd frontend
npm run build          # outputs to frontend/out/
# Then copy out/ to backend/static/ for single-port serving
```

## Deployment

The Docker container deploys to any container platform:

- AWS App Runner
- Render
- Google Cloud Run
- Any OCI-compatible host

## Documentation

- `planning/PLAN.md` — Canonical v1 scope specification
- `planning/API_CONTRACTS.md` — Full API schemas and SSE wire format
- `planning/FRONTEND_SPEC.md` — Frontend design system and component inventory

---

**Note:** This is a simulated trading environment with virtual money. No real financial transactions occur. For educational purposes only.
