# Quick Start Guide - Running E2E Tests

## Prerequisites Check

```bash
# 1. Check Node.js version (requires 20+)
node --version

# 2. Check if backend dependencies are installed
cd ../backend
uv --version

# 3. Return to test directory
cd ../test
```

## Step 1: Install Test Dependencies

```bash
cd test
npm install
```

## Step 2: Install Playwright Browsers

```bash
npx playwright install chromium
```

## Step 3: Set Environment Variables

```bash
# Copy test environment
cp .env.test .env

# Or export directly
export LLM_MOCK=true
export MARKET_SIM_SEED=42
export BASE_URL=http://localhost:8000
```

## Step 4: Run API Implementation Check

This will verify which endpoints are implemented before running full tests:

```bash
npm test -- test-api-check.spec.ts
```

**Expected Output:**
- ✅ marks implemented endpoints
- ❌ marks missing endpoints
- Status codes and response data will be logged

## Step 5: Run Full Test Suite

```bash
# Run all tests
npm test

# Run specific test file
npm test -- test-fresh-start.spec.ts

# Run with browser visible
npm run test:headed

# Run with debugging
npm run test:debug
```

## Interpreting Results

### Success Output
```
✓ test-fresh-start.spec.ts:15:3 › should load homepage (2.5s)
✓ test-fresh-start.spec.ts:25:3 › should display all 10 default tickers (1.2s)
...
58 passed (45.2s)
```

### Failure Output
```
✗ test-trading.spec.ts:10:3 › should buy shares (3.1s)
    Error: Timed out waiting for selector [data-ticker-price]
```

**Common Failures:**
1. **Selector not found** - Frontend missing data-testid attributes
2. **API not implemented** - Backend endpoint missing
3. **Timeout** - Server not running or slow response
4. **Connection refused** - Backend not started

## Troubleshooting

### Issue: "Connection refused"
**Cause:** Backend server not running

**Fix:**
```bash
# Start backend manually
cd ../backend
uv run start_server.py

# Or let Playwright auto-start (configured in playwright.config.ts)
```

### Issue: "LLM_MOCK not set"
**Cause:** Mock mode not enabled

**Fix:**
```bash
export LLM_MOCK=true
npm test
```

### Issue: Tests timeout
**Cause:** Slow server or missing endpoints

**Fix:**
```bash
# Increase timeout in playwright.config.ts
timeout: 120000
```

### Issue: Frontend selectors not found
**Cause:** Frontend not implemented or missing data-testid

**Fix:**
```bash
# Add data-testid attributes to frontend components
# Example:
<div data-testid="watchlist-item" data-ticker="AAPL">
  <span data-ticker-price>$190.50</span>
</div>
```

## Test Execution Modes

### 1. API Check Only (Fastest)
```bash
npm test -- test-api-check.spec.ts
```
Checks which endpoints are implemented without running full E2E tests.

### 2. Single Test Suite
```bash
npm test -- test-fresh-start.spec.ts
```
Run one test file at a time for faster debugging.

### 3. With Browser Visible
```bash
npm run test:headed
```
See the browser while tests run (good for debugging).

### 4. Debug Mode
```bash
npm run test:debug
```
Pause execution and open debugger for step-through debugging.

### 5. Test UI Mode
```bash
npm run test:ui
```
Run tests with Playwright's Test UI for better visualization.

## Viewing Reports

After tests run:

```bash
# Open HTML report
npm run report

# View JSON results
cat test-results/results.json
```

## CI/CD Integration

For GitHub Actions:

```yaml
name: E2E Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - name: Install dependencies
        run: |
          cd test
          npm install
      - name: Install Playwright browsers
        run: |
          cd test
          npx playwright install --with-deps chromium
      - name: Run tests
        run: |
          cd test
          LLM_MOCK=true MARKET_SIM_SEED=42 npm test
      - name: Upload test results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: test-results
          path: test/test-results/
```

## Next Steps After Running Tests

1. **Check TEST_STATUS.md** - Review implementation status
2. **Fix Failed Tests** - Implement missing functionality
3. **Add Data Attributes** - Add data-testid to frontend
4. **Update Tests** - Adjust selectors as needed
5. **Re-run Tests** - Verify fixes

## Quick Reference

| Command | Purpose |
|---------|---------|
| `npm test` | Run all tests |
| `npm test -- test-api-check.spec.ts` | Check API implementation |
| `npm run test:headed` | See browser while testing |
| `npm run test:debug` | Debug mode |
| `npm run report` | View HTML report |
| `LLM_MOCK=true npm test` | Run with mock LLM |

## Need Help?

1. Check `TEST_STATUS.md` for implementation status
2. Check `README.md` for detailed documentation
3. Review test code in `tests/*.spec.ts`
4. Check backend logs for errors
5. Verify environment variables are set correctly
