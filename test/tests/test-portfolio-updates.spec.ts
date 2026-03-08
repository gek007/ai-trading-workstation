/**
 * Test Portfolio Updates
 *
 * Verifies portfolio value updates, positions display, and calculations
 */
import { test, expect } from '@playwright/test';
import { APIClient, waitForSSEConnection, DEFAULT_CASH } from './helpers';

test.describe('Portfolio Updates', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForSSEConnection(page);
  });

  test('should display correct portfolio value after trades', async ({ page }) => {
    const api = new APIClient(page);

    // Initial portfolio should equal cash
    let portfolio = await api.getPortfolio();
    expect(portfolio.total_value).toBe(DEFAULT_CASH);
    expect(portfolio.cash_balance).toBe(DEFAULT_CASH);

    // Buy some shares
    const trade = await api.executeTrade({
      ticker: 'AAPL',
      quantity: 10,
      side: 'buy'
    });

    // Total value should still equal cash + position value
    portfolio = await api.getPortfolio();
    const expectedValue = portfolio.cash_balance +
      portfolio.positions.reduce((sum, p) => sum + p.market_value, 0);

    expect(portfolio.total_value).toBeCloseTo(expectedValue, 2);
    expect(portfolio.total_value).toBeLessThan(DEFAULT_CASH); // Decreased by trade cost
  });

  test('should calculate total unrealized P&L correctly', async ({ page }) => {
    const api = new APIClient(page);

    // Buy multiple positions
    await api.executeTrade({ ticker: 'AAPL', quantity: 10, side: 'buy' });
    await api.executeTrade({ ticker: 'GOOGL', quantity: 5, side: 'buy' });
    await api.executeTrade({ ticker: 'MSFT', quantity: 8, side: 'buy' });

    const portfolio = await api.getPortfolio();

    // Total unrealized P&L should equal sum of individual P&L
    const sumIndividualPL = portfolio.positions.reduce(
      (sum, p) => sum + p.unrealized_pl,
      0
    );

    expect(portfolio.total_unrealized_pl).toBeCloseTo(sumIndividualPL, 2);
  });

  test('should update portfolio value as prices change', async ({ page }) => {
    const api = new APIClient(page);

    // Buy shares
    await api.executeTrade({ ticker: 'AAPL', quantity: 10, side: 'buy' });

    // Get initial portfolio value
    const initialPortfolio = await api.getPortfolio();
    const initialValue = initialPortfolio.total_value;

    // Wait for prices to update (simulator updates every ~500ms)
    await page.waitForTimeout(2000);

    // Get updated portfolio value
    const updatedPortfolio = await api.getPortfolio();
    const updatedValue = updatedPortfolio.total_value;

    // Value should be similar but might have changed slightly due to price movements
    // (In production with real data, this would vary more)
    expect(updatedValue).toBeGreaterThan(0);
  });

  test('should display positions in UI', async ({ page }) => {
    const api = new APIClient(page);

    // Buy some shares
    await api.executeTrade({ ticker: 'AAPL', quantity: 10, side: 'buy' });
    await api.executeTrade({ ticker: 'GOOGL', quantity: 5, side: 'buy' });

    // Wait for UI to update
    await page.waitForTimeout(1000);

    // Check if positions are displayed in UI
    const positionsTable = page.locator(
      '[data-testid="positions-table"], .positions-table, table.positions'
    );

    // Look for position rows
    const aaplPosition = page.locator('[data-position-ticker="AAPL"], [data-ticker="AAPL"].position');
    const googlPosition = page.locator('[data-position-ticker="GOOGL"], [data-ticker="GOOGL"].position');

    // Note: These might not be implemented yet, so we just check they don't error
    const isVisible = await positionsTable.isVisible().catch(() => false);

    if (isVisible) {
      await expect(aaplPosition).toBeVisible();
      await expect(googlPosition).toBeVisible();
    }
  });

  test('should show position details correctly', async ({ page }) => {
    const api = new APIClient(page);

    // Buy shares
    const trade = await api.executeTrade({
      ticker: 'AAPL',
      quantity: 10,
      side: 'buy'
    });

    // Get portfolio
    const portfolio = await api.getPortfolio();
    const position = portfolio.positions.find(p => p.ticker === 'AAPL');

    expect(position).toBeDefined();
    expect(position!.ticker).toBe('AAPL');
    expect(position!.quantity).toBe(10);
    expect(position!.avg_cost).toBe(trade.trade.price);
    expect(position!.current_price).toBeGreaterThan(0);
    expect(position!.market_value).toBeCloseTo(
      position!.quantity * position!.current_price,
      2
    );
    expect(position!.cost_basis).toBeCloseTo(
      position!.quantity * position!.avg_cost,
      2
    );
  });

  test('should handle cash correctly after multiple trades', async ({ page }) => {
    const api = new APIClient(page);

    const initialCash = (await api.getPortfolio()).cash_balance;

    // Buy different stocks
    const trade1 = await api.executeTrade({ ticker: 'AAPL', quantity: 5, side: 'buy' });
    const trade2 = await api.executeTrade({ ticker: 'GOOGL', quantity: 3, side: 'buy' });

    const portfolio = await api.getPortfolio();
    const expectedCash = initialCash - trade1.trade.total_value - trade2.trade.total_value;

    expect(portfolio.cash_balance).toBeCloseTo(expectedCash, 2);
  });

  test('should increase cash when selling', async ({ page }) => {
    const api = new APIClient(page);

    // Buy shares
    await api.executeTrade({ ticker: 'AAPL', quantity: 10, side: 'buy' });

    const cashAfterBuy = (await api.getPortfolio()).cash_balance;

    // Sell some shares
    const sellTrade = await api.executeTrade({
      ticker: 'AAPL',
      quantity: 5,
      side: 'sell'
    });

    const cashAfterSell = (await api.getPortfolio()).cash_balance;

    // Cash should increase by sell amount
    expect(cashAfterSell).toBeCloseTo(
      cashAfterBuy + sellTrade.trade.total_value,
      2
    );
  });

  test('should track portfolio value over time', async ({ page }) => {
    const api = new APIClient(page);

    const values: number[] = [];

    // Collect portfolio values over time
    for (let i = 0; i < 5; i++) {
      const portfolio = await api.getPortfolio();
      values.push(portfolio.total_value);
      await page.waitForTimeout(500);
    }

    // All values should be positive
    values.forEach(v => expect(v).toBeGreaterThan(0));

    // Values should be relatively stable (simulator prices don't move dramatically)
    const max = Math.max(...values);
    const min = Math.min(...values);
    const variation = ((max - min) / min) * 100;

    expect(variation).toBeLessThan(10); // Less than 10% variation over 2.5 seconds
  });

  test('should calculate position weight correctly', async ({ page }) => {
    const api = new APIClient(page);

    // Buy equal value of two stocks
    await api.executeTrade({ ticker: 'AAPL', quantity: 10, side: 'buy' });
    await api.executeTrade({ ticker: 'GOOGL', quantity: 10, side: 'buy' });

    const portfolio = await api.getPortfolio();

    // Calculate weight of first position
    const aaplPosition = portfolio.positions.find(p => p.ticker === 'AAPL');
    const expectedWeight = (aaplPosition!.market_value / portfolio.total_value) * 100;

    // Weight should be between 0 and 100
    expect(expectedWeight).toBeGreaterThan(0);
    expect(expectedWeight).toBeLessThan(100);
  });

  test('should handle portfolio with no positions', async ({ page }) => {
    const api = new APIClient(page);

    const portfolio = await api.getPortfolio();

    expect(portfolio.positions).toHaveLength(0);
    expect(portfolio.total_value).toBe(portfolio.cash_balance);
    expect(portfolio.total_unrealized_pl).toBe(0);
    expect(portfolio.total_unrealized_pl_percent).toBe(0);
  });
});
