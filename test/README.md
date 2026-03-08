# FinAlly E2E Tests

End-to-end tests for the FinAlly AI Trading Workstation using Playwright.

## Prerequisites

- Node.js 20+
- Backend server running (or use auto-start via playwright.config.ts)

## Setup

```bash
# Install dependencies
npm install

# Install Playwright browsers
npx playwright install chromium
```

## Running Tests

### Run all tests
```bash
npm test
```

### Run tests in headed mode (see browser)
```bash
npm run test:headed
```

### Debug tests
```bash
npm run test:debug
```

### Run with UI
```bash
npm run test:ui
```

## Test Files

- `test-fresh-start.spec.ts` - Verifies default watchlist, $10k balance, streaming prices
- `test-watchlist-crud.spec.ts` - Tests adding/removing tickers
- `test-trading.spec.ts` - Tests buy/sell operations and edge cases
- `test-portfolio-updates.spec.ts` - Tests portfolio calculations and display
- `test-chat-mock.spec.ts` - Tests AI chat with mock mode (requires LLM_MOCK=true)
- `test-sse-resilience.spec.ts` - Tests SSE reconnection and error handling

## Environment Variables

Copy `.env.test` to `.env` and configure:

```bash
# Required for deterministic tests
LLM_MOCK=true
MARKET_SIM_SEED=42

# Optional: Override default base URL
BASE_URL=http://localhost:8000
```

## Auto-Start Server

The `playwright.config.ts` is configured to automatically start the backend server:

```typescript
webServer: {
  command: 'cd ../backend && uv run start_server.py',
  url: 'http://localhost:8000',
  reuseExistingServer: !process.env.CI,
}
```

If you have a server already running, it will use that instead.

## Test Data

Tests use the default seed data:
- Default tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX
- Default cash: $10,000
- Deterministic prices via MARKET_SIM_SEED=42

## Test Isolation

- Tests run sequentially (workers: 1) to avoid state conflicts
- Each test expects a fresh state
- Some tests may fail if run multiple times without cleanup

## CI/CD

For CI environments:

```bash
# Install dependencies
npm install

# Install Playwright browsers
npx playwright install --with-deps chromium

# Run tests
CI=true npm test
```

## Troubleshooting

### Tests fail with "connection refused"
- Ensure backend server is running
- Check BASE_URL environment variable
- Verify port 8000 is available

### Tests fail with "timeout"
- Increase timeout in playwright.config.ts
- Check backend logs for errors
- Verify database is initialized

### Chat tests fail
- Ensure LLM_MOCK=true is set
- Check backend supports mock mode

### Price tests are flaky
- Ensure MARKET_SIM_SEED=42 is set for deterministic prices
- Increase wait times for SSE updates

## Test Reports

After running tests:

```bash
# View HTML report
npm run report
```

Reports are generated in `test-results/` directory.
