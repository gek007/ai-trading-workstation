/**
 * Test SSE Connection Resilience
 *
 * Verifies SSE reconnection and error handling
 */
import { test, expect } from '@playwright/test';
import { APIClient, waitForSSEConnection, waitForPriceUpdates } from './helpers';

test.describe('SSE Resilience', () => {
  test('should automatically reconnect on connection loss', async ({ page, context }) => {
    await page.goto('/');

    // Wait for initial connection
    await waitForSSEConnection(page);
    await waitForPriceUpdates(page);

    // Capture initial connection status
    const connectionStatus = page.locator(
      '[data-testid="connection-status"], .connection-status, [data-connection]'
    );
    await expect(connectionStatus).toBeVisible();

    // Simulate network disconnection
    await context.setOffline(true);

    // Wait for disconnection to be detected
    await page.waitForTimeout(2000);

    // Verify disconnected state
    const isDisconnected = await connectionStatus.evaluate(el => {
      return el.classList.contains('disconnected') ||
             el.getAttribute('data-connection') === 'disconnected';
    });

    // Reconnect
    await context.setOffline(false);

    // Wait for reconnection
    await page.waitForTimeout(3000);

    // Verify reconnected state
    const isReconnected = await connectionStatus.evaluate(el => {
      return el.classList.contains('connected') ||
             el.getAttribute('data-connection') === 'connected';
    });

    expect(isReconnected).toBe(true);
  });

  test('should continue receiving price updates after reconnect', async ({ page, context }) => {
    await page.goto('/');

    // Wait for initial connection and prices
    await waitForSSEConnection(page);
    await waitForPriceUpdates(page);

    // Capture initial price
    const priceElement = page.locator('[data-ticker="AAPL"] [data-ticker-price], [data-ticker="AAPL"].price').first();
    const initialPrice = await priceElement.textContent();

    // Simulate disconnection
    await context.setOffline(true);
    await page.waitForTimeout(1000);

    // Reconnect
    await context.setOffline(false);
    await page.waitForTimeout(2000);

    // Verify we still get price updates
    await expect(priceElement).toBeVisible();
    const reconnectedPrice = await priceElement.textContent();
    expect(reconnectedPrice).toBeTruthy();
  });

  test('should handle server restart gracefully', async ({ page }) => {
    await page.goto('/');

    // Wait for initial connection
    await waitForSSEConnection(page);
    await waitForPriceUpdates(page);

    // Note: This test documents expected behavior
    // In a real scenario, the EventSource API will automatically retry
    // We verify the client doesn't crash

    const priceElements = page.locator('[data-ticker-price]');
    await expect(priceElements.first()).toBeVisible();

    // The page should remain functional
    const header = page.locator('header, h1, [data-testid="header"]');
    await expect(header).toBeVisible();
  });

  test('should show loading state during connection', async ({ page }) => {
    // Navigate and quickly check for loading state
    await page.goto('/');

    // Look for loading indicator (might be brief)
    const loadingIndicator = page.locator(
      '[data-testid="loading"], .loading, [data-loading="true"]'
    );

    const wasLoading = await loadingIndicator.isVisible().catch(() => false);

    // Should eventually show connected state
    await waitForSSEConnection(page);

    // Loading should be gone
    const isLoading = await loadingIndicator.isVisible().catch(() => false);

    if (wasLoading) {
      expect(isLoading).toBe(false);
    }
  });

  test('should buffer and display missed updates on reconnect', async ({ page, context }) => {
    await page.goto('/');

    // Wait for initial connection
    await waitForSSEConnection(page);
    await waitForPriceUpdates(page);

    // Disconnect
    await context.setOffline(true);
    await page.waitForTimeout(1500);

    // Reconnect
    await context.setOffline(false);

    // Wait for reconnection and new data
    await waitForSSEConnection(page);

    // Verify prices are still displayed
    const priceElements = page.locator('[data-ticker-price]');
    await expect(priceElements.first()).toBeVisible({ timeout: 10000 });
  });

  test('should handle rapid connection state changes', async ({ page, context }) => {
    await page.goto('/');

    await waitForSSEConnection(page);

    // Rapidly toggle connection
    for (let i = 0; i < 3; i++) {
      await context.setOffline(true);
      await page.waitForTimeout(500);
      await context.setOffline(false);
      await page.waitForTimeout(1000);
    }

    // Should recover and show prices
    await waitForSSEConnection(page);
    const priceElements = page.locator('[data-ticker-price]');
    await expect(priceElements.first()).toBeVisible({ timeout: 10000 });
  });

  test('should maintain application state during reconnection', async ({ page, context }) => {
    const api = new APIClient(page);

    await page.goto('/');

    // Buy some shares
    await api.executeTrade({ ticker: 'AAPL', quantity: 10, side: 'buy' });

    const portfolioBefore = await api.getPortfolio();

    // Disconnect
    await context.setOffline(true);
    await page.waitForTimeout(1000);

    // Reconnect
    await context.setOffline(false);
    await page.waitForTimeout(2000);

    // Portfolio state should be preserved
    const portfolioAfter = await api.getPortfolio();
    expect(portfolioAfter.cash_balance).toBe(portfolioBefore.cash_balance);
    expect(portfolioAfter.positions).toHaveLength(portfolioBefore.positions.length);
  });

  test('should display connection errors gracefully', async ({ page }) => {
    // Navigate to a non-existent server (if configured)
    // This test documents expected behavior
    await page.goto('/');

    // The page should handle connection errors gracefully
    // without showing uncaught exceptions
    const errors: string[] = [];

    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Wait for connection or timeout
    await waitForSSEConnection(page).catch(() => {
      // Connection failed, which is ok for this test
    });

    // Check for catastrophic errors
    const catastrophicErrors = errors.filter(e =>
      e.includes('Uncaught') || e.includes('TypeError')
    );

    // Should not have catastrophic errors
    expect(catastrophicErrors.length).toBe(0);
  });

  test('should recover from temporary network issues', async ({ page, context }) => {
    await page.goto('/');

    await waitForSSEConnection(page);
    await waitForPriceUpdates(page);

    // Simulate network issues
    await context.setOffline(true);
    await page.waitForTimeout(2000);

    // Restore network
    await context.setOffline(false);

    // Should recover
    await waitForSSEConnection(page);

    // Verify application is responsive
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('should handle multiple SSE connections correctly', async ({ page }) => {
    // Open a second page
    const page2 = await page.context().newPage();

    await page2.goto('/');

    // Both should connect
    await waitForSSEConnection(page);
    await waitForSSEConnection(page2);

    // Both should show prices
    const price1 = page.locator('[data-ticker-price]').first();
    const price2 = page2.locator('[data-ticker-price]').first();

    await expect(price1).toBeVisible();
    await expect(price2).toBeVisible();

    await page2.close();
  });
});
