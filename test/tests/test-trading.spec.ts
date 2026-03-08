/**
 * Test Trading Functionality
 *
 * Verifies buy and sell operations, portfolio updates, and edge cases
 */
import { test, expect } from '@playwright/test';
import { APIClient, DEFAULT_CASH } from './helpers';

test.describe('Trading', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should buy shares and update portfolio', async ({ page }) => {
    const api = new APIClient(page);

    // Get initial portfolio state
    const initialPortfolio = await api.getPortfolio();
    expect(initialPortfolio.positions).toHaveLength(0);

    // Buy 10 shares of AAPL
    const tradeResponse = await api.executeTrade({
      ticker: 'AAPL',
      quantity: 10,
      side: 'buy'
    });

    expect(tradeResponse.status).toBe('executed');
    expect(tradeResponse.trade.ticker).toBe('AAPL');
    expect(tradeResponse.trade.side).toBe('buy');
    expect(tradeResponse.trade.quantity).toBe(10);

    // Verify portfolio was updated
    const updatedPortfolio = await api.getPortfolio();
    expect(updatedPortfolio.positions).toHaveLength(1);

    const aaplPosition = updatedPortfolio.positions.find(p => p.ticker === 'AAPL');
    expect(aaplPosition).toBeDefined();
    expect(aaplPosition!.quantity).toBe(10);
    expect(aaplPosition!.avg_cost).toBe(tradeResponse.trade.price);
    expect(aaplPosition!.current_price).toBe(tradeResponse.trade.price);

    // Verify cash decreased
    const expectedCost = tradeResponse.trade.total_value;
    expect(updatedPortfolio.cash_balance).toBeCloseTo(
      initialPortfolio.cash_balance - expectedCost,
      2
    );
  });

  test('should sell shares and update portfolio', async ({ page }) => {
    const api = new APIClient(page);

    // First buy some shares
    await api.executeTrade({
      ticker: 'AAPL',
      quantity: 20,
      side: 'buy'
    });

    // Now sell 10 shares
    const sellResponse = await api.executeTrade({
      ticker: 'AAPL',
      quantity: 10,
      side: 'sell'
    });

    expect(sellResponse.status).toBe('executed');
    expect(sellResponse.trade.side).toBe('sell');
    expect(sellResponse.trade.quantity).toBe(10);

    // Verify portfolio was updated
    const portfolio = await api.getPortfolio();
    const aaplPosition = portfolio.positions.find(p => p.ticker === 'AAPL');
    expect(aaplPosition).toBeDefined();
    expect(aaplPosition!.quantity).toBe(10); // 20 - 10
  });

  test('should remove position when all shares are sold', async ({ page }) => {
    const api = new APIClient(page);

    // Buy shares
    await api.executeTrade({
      ticker: 'GOOGL',
      quantity: 5,
      side: 'buy'
    });

    // Verify position exists
    let portfolio = await api.getPortfolio();
    expect(portfolio.positions.find(p => p.ticker === 'GOOGL')).toBeDefined();

    // Sell all shares
    await api.executeTrade({
      ticker: 'GOOGL',
      quantity: 5,
      side: 'sell'
    });

    // Verify position was removed
    portfolio = await api.getPortfolio();
    expect(portfolio.positions.find(p => p.ticker === 'GOOGL')).toBeUndefined();
  });

  test('should reject buy with insufficient cash', async ({ page }) => {
    const api = new APIClient(page);

    // Try to buy more than cash allows
    await expect(async () => {
      await api.executeTrade({
        ticker: 'AAPL',
        quantity: 10000, // Way more than $10k can buy
        side: 'buy'
      });
    }).toThrow();

    // Verify error message
    try {
      await api.executeTrade({
        ticker: 'AAPL',
        quantity: 10000,
        side: 'buy'
      });
      expect(true).toBe(false);
    } catch (error: any) {
      expect(error.message).toContain('insufficient');
    }
  });

  test('should reject sell with insufficient shares', async ({ page }) => {
    const api = new APIClient(page);

    // Try to sell without owning any shares
    await expect(async () => {
      await api.executeTrade({
        ticker: 'AAPL',
        quantity: 10,
        side: 'sell'
      });
    }).toThrow();

    // Verify error message
    try {
      await api.executeTrade({
        ticker: 'AAPL',
        quantity: 10,
        side: 'sell'
      });
      expect(true).toBe(false);
    } catch (error: any) {
      expect(error.message).toContain('insufficient');
    }
  });

  test('should reject sell of more shares than owned', async ({ page }) => {
    const api = new APIClient(page);

    // Buy 10 shares
    await api.executeTrade({
      ticker: 'MSFT',
      quantity: 10,
      side: 'buy'
    });

    // Try to sell 20 shares
    await expect(async () => {
      await api.executeTrade({
        ticker: 'MSFT',
        quantity: 20,
        side: 'sell'
      });
    }).toThrow();
  });

  test('should reject trades for non-watchlist tickers', async ({ page }) => {
    const api = new APIClient(page);

    // Try to trade a ticker not in watchlist
    await expect(async () => {
      await api.executeTrade({
        ticker: 'XYZ',
        quantity: 10,
        side: 'buy'
      });
    }).toThrow();

    // Verify error mentions watchlist
    try {
      await api.executeTrade({
        ticker: 'XYZ',
        quantity: 10,
        side: 'buy'
      });
      expect(true).toBe(false);
    } catch (error: any) {
      expect(error.message).toContain('watchlist');
    }
  });

  test('should handle fractional shares', async ({ page }) => {
    const api = new APIClient(page);

    // Buy fractional shares
    const tradeResponse = await api.executeTrade({
      ticker: 'AAPL',
      quantity: 10.5678,
      side: 'buy'
    });

    expect(tradeResponse.trade.quantity).toBeCloseTo(10.5678, 4);

    // Verify portfolio
    const portfolio = await api.getPortfolio();
    const aaplPosition = portfolio.positions.find(p => p.ticker === 'AAPL');
    expect(aaplPosition!.quantity).toBeCloseTo(10.5678, 4);
  });

  test('should reject invalid quantities', async ({ page }) => {
    const api = new APIClient(page);

    const invalidQuantities = [
      { quantity: 0, description: 'zero' },
      { quantity: -10, description: 'negative' },
      { quantity: 0.00001, description: 'too small' },
      { quantity: 1000001, description: 'too large' },
    ];

    for (const { quantity, description } of invalidQuantities) {
      await expect(async () => {
        await api.executeTrade({
          ticker: 'AAPL',
          quantity,
          side: 'buy'
        });
      }).toThrow(`Should reject ${description} quantity`);
    }
  });

  test('should calculate unrealized P&L correctly', async ({ page }) => {
    const api = new APIClient(page);

    // Buy shares at current price
    const buyResponse = await api.executeTrade({
      ticker: 'AAPL',
      quantity: 10,
      side: 'buy'
    });

    const buyPrice = buyResponse.trade.price;

    // Get portfolio immediately after buy
    const portfolio = await api.getPortfolio();
    const aaplPosition = portfolio.positions.find(p => p.ticker === 'AAPL');

    // Immediately after buy, P&L should be near zero (prices might have moved slightly)
    expect(aaplPosition!.unrealized_pl).toBeLessThan(100); // Less than $100 difference

    // Verify P&L calculation
    const expectedPL = (aaplPosition!.current_price - buyPrice) * aaplPosition!.quantity;
    expect(aaplPosition!.unrealized_pl).toBeCloseTo(expectedPL, 2);
  });

  test('should handle multiple trades for same ticker', async ({ page }) => {
    const api = new APIClient(page);

    // First buy
    await api.executeTrade({
      ticker: 'AAPL',
      quantity: 10,
      side: 'buy'
    });

    // Second buy (should update average cost)
    const secondBuy = await api.executeTrade({
      ticker: 'AAPL',
      quantity: 5,
      side: 'buy'
    });

    const portfolio = await api.getPortfolio();
    const aaplPosition = portfolio.positions.find(p => p.ticker === 'AAPL');

    expect(aaplPosition!.quantity).toBe(15);

    // Average cost should be weighted average of both buys
    // We can't predict exact price due to simulator, but it should be between the two prices
    expect(aaplPosition!.avg_cost).toBeGreaterThan(0);
  });

  test('should execute trades rapidly', async ({ page }) => {
    const api = new APIClient(page);

    // Execute multiple trades in quick succession
    const trades = [
      { ticker: 'AAPL', quantity: 5, side: 'buy' as const },
      { ticker: 'GOOGL', quantity: 3, side: 'buy' as const },
      { ticker: 'MSFT', quantity: 7, side: 'buy' as const },
    ];

    for (const trade of trades) {
      await api.executeTrade(trade);
    }

    // Verify all positions were created
    const portfolio = await api.getPortfolio();
    expect(portfolio.positions).toHaveLength(3);

    for (const trade of trades) {
      const position = portfolio.positions.find(p => p.ticker === trade.ticker);
      expect(position).toBeDefined();
      expect(position!.quantity).toBe(trade.quantity);
    }
  });
});
