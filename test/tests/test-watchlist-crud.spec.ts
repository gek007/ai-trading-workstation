/**
 * Test Watchlist CRUD Operations
 *
 * Verifies adding and removing tickers from the watchlist
 */
import { test, expect } from '@playwright/test';
import { APIClient, waitForSSEConnection, waitForPriceUpdates } from './helpers';

test.describe('Watchlist CRUD', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForSSEConnection(page);
  });

  test('should add a new ticker to watchlist via API', async ({ page }) => {
    const api = new APIClient(page);

    // Add PYPL to watchlist
    const response = await api.addToWatchlist('PYPL');
    expect(response.status).toBe('added');
    expect(response.ticker).toBe('PYPL');

    // Verify it appears in watchlist
    const watchlist = await api.getWatchlist();
    const tickers = watchlist.tickers.map(t => t.ticker);
    expect(tickers).toContain('PYPL');

    // Verify price is set (simulator should generate price)
    const pyplItem = watchlist.tickers.find(t => t.ticker === 'PYPL');
    expect(pyplItem).toBeDefined();
    expect(pyplItem!.price).toBeGreaterThan(0);
  });

  test('should not add duplicate ticker to watchlist', async ({ page }) => {
    const api = new APIClient(page);

    // Try to add AAPL (already in default watchlist)
    await expect(async () => {
      await api.addToWatchlist('AAPL');
    }).toThrow();

    // Verify error response
    try {
      await api.addToWatchlist('AAPL');
      expect(true).toBe(false); // Should not reach here
    } catch (error: any) {
      expect(error.message).toContain('already');
    }
  });

  test('should remove ticker from watchlist via API', async ({ page }) => {
    const api = new APIClient(page);

    // Remove NFLX from watchlist
    const response = await api.removeFromWatchlist('NFLX');
    expect(response.status).toBe('removed');
    expect(response.ticker).toBe('NFLX');

    // Verify it's no longer in watchlist
    const watchlist = await api.getWatchlist();
    const tickers = watchlist.tickers.map(t => t.ticker);
    expect(tickers).not.toContain('NFLX');
  });

  test('should handle removing non-existent ticker', async ({ page }) => {
    const api = new APIClient(page);

    // Try to remove ticker that doesn't exist
    await expect(async () => {
      await api.removeFromWatchlist('XYZ');
    }).toThrow();

    // Verify error response
    try {
      await api.removeFromWatchlist('XYZ');
      expect(true).toBe(false); // Should not reach here
    } catch (error: any) {
      expect(error.message).toContain('not found');
    }
  });

  test('should reject invalid ticker format', async ({ page }) => {
    const api = new APIClient(page);

    // Test invalid formats
    const invalidTickers = [
      'toolong',   // More than 5 chars
      '123',       // Numbers only
      'aapl',      // Lowercase
      'A$PL',      // Special character
      '',          // Empty
    ];

    for (const ticker of invalidTickers) {
      await expect(async () => {
        await api.addToWatchlist(ticker);
      }).toThrow();
    }
  });

  test('should maintain watchlist state across page reloads', async ({ page }) => {
    const api = new APIClient(page);

    // Get initial watchlist count
    const initialWatchlist = await api.getWatchlist();
    const initialCount = initialWatchlist.tickers.length;

    // Add a ticker
    await api.addToWatchlist('PYPL');

    // Reload page
    await page.reload();
    await waitForSSEConnection(page);

    // Verify new ticker is still there
    const reloadedWatchlist = await api.getWatchlist();
    expect(reloadedWatchlist.tickers).toHaveLength(initialCount + 1);
    expect(reloadedWatchlist.tickers.map(t => t.ticker)).toContain('PYPL');
  });

  test('should handle rapid add/remove operations', async ({ page }) => {
    const api = new APIClient(page);

    // Add multiple tickers rapidly
    const tickersToAdd = ['PYPL', 'INTC', 'AMD'];

    for (const ticker of tickersToAdd) {
      await api.addToWatchlist(ticker);
    }

    // Verify all were added
    const watchlist = await api.getWatchlist();
    const tickers = watchlist.tickers.map(t => t.ticker);
    for (const ticker of tickersToAdd) {
      expect(tickers).toContain(ticker);
    }

    // Remove them rapidly
    for (const ticker of tickersToAdd) {
      await api.removeFromWatchlist(ticker);
    }

    // Verify all were removed
    const finalWatchlist = await api.getWatchlist();
    const finalTickers = finalWatchlist.tickers.map(t => t.ticker);
    for (const ticker of tickersToAdd) {
      expect(finalTickers).not.toContain(ticker);
    }
  });
});
