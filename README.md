# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades via natural language.

Built entirely by coding agents as a capstone project for an agentic AI coding course, demonstrating how orchestrated AI agents can produce a production-quality full-stack application.

## 🎯 What It Does

FinAlly provides a complete trading terminal experience with:

- **Live Price Streaming** — Real-time market data via Server-Sent Events (SSE) with green/red flash animations on price changes
- **Portfolio Simulation** — Start with $10,000 virtual cash, trade market orders with instant fills, no fees
- **Interactive Charts** — Sparkline mini-charts in watchlist, detailed main chart for selected ticker
- **Portfolio Visualizations** — Heatmap (treemap) sized by position weight and colored by P&L, positions table with unrealized P&L
- **AI Chat Assistant** — Natural language interface to analyze holdings, get suggestions, and auto-execute trades
- **Watchlist Management** — Add/remove tickers manually or via AI chat
- **Dark Terminal Aesthetic** — Bloomberg-inspired, data-dense layout optimized for desktop

## 🏗️ Architecture

Single-container, single-port architecture for simplicity:

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Frontend** | Next.js + TypeScript (static export) | Single origin, no CORS, one port, simple deployment |
| **Backend** | FastAPI (Python/uv) | Modern async Python, fast development, uv for reproducible deps |
| **Database** | SQLite | Self-contained, zero config, perfect for single-user |
| **Real-time** | Server-Sent Events (SSE) | One-way push, simpler than WebSockets, universal browser support |
| **AI** | LiteLLM → OpenRouter (Cerebras) | Fast inference, structured outputs for trade execution |
| **Market Data** | GBM Simulator (default) / Massive API | Built-in simulator for demo, optional real data |

### Design Decisions

- **SSE over WebSockets** — One-way push is all we need; simpler implementation
- **SQLite over Postgres** — No auth/multi-user in v1, self-contained, zero setup
- **Market orders only** — Eliminates order book, limit orders, partial fills — dramatically simpler
- **Auto-execution trades** — Simulated environment, zero stakes, demonstrates agentic AI capabilities

## 🚀 Quick Start

### Prerequisites

- Docker installed locally
- OpenRouter API key ([get one here](https://openrouter.ai/))

### macOS/Linux

```bash
# 1. Clone the repository
git clone <repo-url>
cd finally

# 2. Configure environment
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# 3. Start the application
./scripts/start_mac.sh

# 4. Open browser to http://localhost:8000
```

### Windows (PowerShell)

```powershell
# 1. Clone the repository
git clone <repo-url>
cd finally

# 2. Configure environment
copy .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# 3. Start the application
.\scripts\start_windows.ps1

# 4. Open browser to http://localhost:8000
```

### Stopping the Application

**macOS/Linux:** `./scripts/stop_mac.sh`
**Windows:** `.\scripts\stop_windows.ps1`

The SQLite database persists via Docker volume, so your portfolio and trades are saved between runs.

## ⚙️ Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | ✅ Yes | - | OpenRouter API key for AI chat functionality |
| `MASSIVE_API_KEY` | No | - | Massive (Polygon.io) API key for real market data. If omitted, uses built-in GBM simulator |
| `LLM_MOCK` | No | `false` | Set to `true` for deterministic mock LLM responses (useful for testing) |
| `MARKET_SIM_SEED` | No | - | Seed for deterministic simulator price sequences (useful for reproducible tests) |

## 📁 Project Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
│   ├── src/
│   ├── package.json
│   └── tsconfig.json
├── backend/                  # FastAPI uv project (Python)
│   ├── app/
│   ├── pyproject.toml
│   └── db/                   # Database schema and runtime DB
│       ├── schema.sql        # Database schema (committed)
│       ├── seed.sql          # Default seed data (committed)
│       └── finally.db        # Runtime database (gitignored, volume-mounted)
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # Canonical v1 scope specification
│   ├── API_CONTRACTS.md      # API schemas and SSE wire format
│   └── ...                   # Additional agent reference docs
├── test/                     # Playwright E2E tests
│   ├── tests/
│   └── docker-compose.test.yml
├── scripts/                  # Start/stop scripts
│   ├── start_mac.sh          # Launch Docker container (macOS/Linux)
│   ├── stop_mac.sh           # Stop Docker container (macOS/Linux)
│   ├── start_windows.ps1     # Launch Docker container (Windows)
│   └── stop_windows.ps1      # Stop Docker container (Windows)
├── Dockerfile                # Multi-stage build (Node → Python)
├── docker-compose.yml        # Optional convenience wrapper
├── .env                      # Environment variables (gitignored)
├── .env.example              # Environment variable template
└── README.md                 # This file
```

### Key Boundaries

- **`frontend/`** — Self-contained Next.js project, talks to backend via `/api/*` endpoints
- **`backend/`** — Self-contained uv project, owns all server logic, DB initialization, API routes, SSE streaming, market data, LLM integration
- **`backend/db/`** — Schema definitions, seed data, runtime SQLite database (Docker volume-mounted for persistence)
- **`planning/`** — Project-wide documentation, shared contract for all agents

## 🔌 API Endpoints

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
| GET | `/api/health` | Health check for Docker/deployment |

## 🎨 Visual Design

### Color Scheme

| Usage | Color | Hex |
|-------|-------|-----|
| Background (dark) | Deep blue/gray | `#0d1117`, `#1a1a2e` |
| Accent (yellow) | Gold/amber | `#ecad0a` |
| Primary (blue) | Sky blue | `#209dd7` |
| Secondary (purple) | Royal purple | `#753991` |
| Price up | Green | `#00c853` |
| Price down | Red | `#ff1744` |

### UI Elements

- **Watchlist Panel** — Grid/table with ticker, price (flashing), change %, sparkline mini-chart
- **Main Chart Area** — Large detailed chart for selected ticker, updates in real-time
- **Portfolio Heatmap** — Treemap visualization (size = weight, color = P&L)
- **Positions Table** — Ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Trade Bar** — Ticker input, quantity input, buy/sell buttons
- **AI Chat Panel** — Collapsible sidebar with conversation history and trade confirmations
- **Header** — Portfolio value (live), connection status indicator, cash balance

## 🤖 AI Chat Assistant

The LLM can:

- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when you ask or agree
- Manage the watchlist proactively
- Provide data-driven insights

### Structured Output

The LLM responds with JSON:

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

Trades execute automatically — no confirmation dialog (it's a simulated environment with fake money).

## 💾 Database

SQLite with lazy initialization — the backend creates and seeds the database on first run.

### Schema

| Table | Description |
|-------|-------------|
| `users_profile` | User state (cash balance) |
| `watchlist` | Tickers being watched |
| `positions` | Current holdings |
| `trades` | Trade history (append-only log) |
| `chat_messages` | Conversation history with LLM |

All tables include `user_id` (default: `"default"`) for future multi-user support.

### Seed Data

- $10,000 starting cash
- Default watchlist: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

## 🧪 Testing

### Unit Tests

- **Backend (pytest)** — Market data simulator, portfolio logic, P&L calculations, LLM parsing, API routes
- **Frontend (React Testing Library)** — Component rendering, price animations, watchlist CRUD, portfolio display

### E2E Tests

Playwright tests in `test/` cover:
- Fresh start experience (default watchlist, balance, streaming prices)
- Watchlist CRUD operations
- Buy/sell trades
- Portfolio visualization
- AI chat (with mock mode)
- SSE reconnection resilience

## 📊 Market Data

### Simulator (Default)

- Geometric Brownian Motion (GBM) with configurable drift/volatility
- Updates at ~500ms intervals
- Correlated moves across tickers (tech stocks move together)
- Occasional random "events" — sudden 2-5% moves for drama
- Realistic seed prices (AAPL ~$190, GOOGL ~$175, etc.)

### Real Data (Optional)

Set `MASSIVE_API_KEY` to use Massive (Polygon.io) polling instead of the simulator.

## 🚀 Deployment

The container is designed to deploy to:
- AWS App Runner
- Render
- Google Cloud Run
- Any container platform

A Terraform configuration for App Runner may be provided as a stretch goal.

## 📖 Documentation

- **`planning/PLAN.md`** — Canonical v1 scope specification
- **`planning/API_CONTRACTS.md`** — API schemas, SSE format, trade validation
- **`planning/`** — Additional agent reference documentation

## 🛠️ Development

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Backend Development

```bash
cd backend
uv sync
uvicorn app.main:app --reload
```

## 📝 License

See [LICENSE](LICENSE).

## 🙏 Acknowledgments

Built as a capstone project for an agentic AI coding course, demonstrating how orchestrated AI agents can collaborate to produce a production-quality full-stack application.

---

**Note:** This is a simulated trading environment with virtual money. No real financial transactions occur. For educational purposes only.
