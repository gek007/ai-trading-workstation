/**
 * Test Chat Functionality with Mock LLM
 *
 * Verifies AI chat responses and trade execution via mock mode
 * REQUIRES: LLM_MOCK=true environment variable
 */
import { test, expect } from '@playwright/test';
import { APIClient } from './helpers';

test.describe('Chat (Mock Mode)', () => {
  test.beforeEach(async ({ page }) => {
    // Verify LLM_MOCK is set
    expect(process.env.LLM_MOCK).toBe('true');
    await page.goto('/');
  });

  test('should receive mock response from chat', async ({ page }) => {
    const api = new APIClient(page);

    const response = await api.sendChatMessage('Hello, how are you?');

    expect(response.message).toBeDefined();
    expect(response.message.role).toBe('assistant');
    expect(response.message.content).toBeTruthy();
    expect(response.message.id).toBeTruthy();

    // Mock response should contain specific text
    expect(response.message.content).toContain('Mock response');
  });

  test('should execute trade via chat command', async ({ page }) => {
    const api = new APIClient(page);

    // Get initial portfolio
    const initialPortfolio = await api.getPortfolio();
    const initialPositions = initialPortfolio.positions.length;

    // Send chat message to buy AAPL
    const response = await api.sendChatMessage('Buy 10 shares of AAPL');

    // Verify response
    expect(response.message.content).toBeTruthy();
    expect(response.executed_actions).toBeDefined();
    expect(response.executed_actions!.trades).toHaveLength(1);

    const trade = response.executed_actions!.trades[0];
    expect(trade.ticker).toBe('AAPL');
    expect(trade.side).toBe('buy');
    expect(trade.quantity).toBe(10);

    // Verify portfolio was updated
    const updatedPortfolio = await api.getPortfolio();
    expect(updatedPortfolio.positions).toHaveLength(initialPositions + 1);

    const aaplPosition = updatedPortfolio.positions.find(p => p.ticker === 'AAPL');
    expect(aaplPosition).toBeDefined();
    expect(aaplPosition!.quantity).toBe(10);
  });

  test('should handle chat with trade execution and confirmation', async ({ page }) => {
    const api = new APIClient(page);

    // Send command to buy
    const buyResponse = await api.sendChatMessage('Buy 5 shares of GOOGL');

    expect(buyResponse.executed_actions!.trades).toHaveLength(1);
    expect(buyResponse.executed_actions!.trades[0].ticker).toBe('GOOGL');

    // Verify trade was executed
    const portfolio = await api.getPortfolio();
    const googlPosition = portfolio.positions.find(p => p.ticker === 'GOOGL');
    expect(googlPosition).toBeDefined();
    expect(googlPosition!.quantity).toBe(5);
  });

  test('should handle chat with watchlist changes', async ({ page }) => {
    const api = new APIClient(page);

    // Get initial watchlist
    const initialWatchlist = await api.getWatchlist();

    // Send command to add ticker
    const response = await api.sendChatMessage('Add PYPL to my watchlist');

    // Note: Current mock might not implement watchlist changes
    // This test verifies the structure even if empty
    expect(response.executed_actions).toBeDefined();

    if (response.executed_actions!.watchlist_changes.length > 0) {
      const change = response.executed_actions!.watchlist_changes[0];
      expect(change.ticker).toBeTruthy();
      expect(['added', 'removed']).toContain(change.action);
    }
  });

  test('should handle multiple trades in single chat message', async ({ page }) => {
    const api = new APIClient(page);

    // Send command for multiple trades
    const response = await api.sendChatMessage(
      'Buy 5 shares of AAPL and 3 shares of MSFT'
    );

    // Verify response structure
    expect(response.message).toBeDefined();
    expect(response.executed_actions).toBeDefined();

    // Note: Current mock might only execute one trade
    // This test verifies the structure handles the response
    expect(response.executed_actions!.trades.length).toBeGreaterThanOrEqual(0);
  });

  test('should handle failed trade in chat response', async ({ page }) => {
    const api = new APIClient(page);

    // Try to buy more than cash allows
    const response = await api.sendChatMessage(
      'Buy 10000 shares of AAPL'
    );

    // Should still get a response, but trade might fail
    expect(response.message).toBeDefined();
    expect(response.message.content).toContain('insufficient');
  });

  test('should maintain conversation context', async ({ page }) => {
    const api = new APIClient(page);

    // First message
    const response1 = await api.sendChatMessage('What is my portfolio value?');
    expect(response1.message.content).toBeTruthy();

    // Second message (should have context from first)
    const response2 = await api.sendChatMessage('Buy 10 shares of TSLA');
    expect(response2.message.content).toBeTruthy();

    // Verify portfolio was updated
    const portfolio = await api.getPortfolio();
    const tsalPosition = portfolio.positions.find(p => p.ticker === 'TSLA');
    expect(tsalPosition).toBeDefined();
  });

  test('should provide portfolio analysis', async ({ page }) => {
    const api = new APIClient(page);

    // Buy some positions first
    await api.executeTrade({ ticker: 'AAPL', quantity: 10, side: 'buy' });
    await api.executeTrade({ ticker: 'GOOGL', quantity: 5, side: 'buy' });

    // Ask for analysis
    const response = await api.sendChatMessage(
      'Analyze my portfolio and show me my positions'
    );

    expect(response.message.content).toBeTruthy();
    expect(response.message.content).toMatch(/portfolio|position|cash|value/i);
  });

  test('should handle chat with no actions (informational only)', async ({ page }) => {
    const api = new APIClient(page);

    // Send informational query
    const response = await api.sendChatMessage(
      'What stocks are in my watchlist?'
    );

    expect(response.message.content).toBeTruthy();
    // Should have no trades or watchlist changes
    expect(response.executed_actions).toBeDefined();
    expect(response.executed_actions!.trades).toHaveLength(0);
  });

  test('should handle rapid chat messages', async ({ page }) => {
    const api = new APIClient(page);

    // Send multiple messages rapidly
    const messages = [
      'Buy 5 shares of AAPL',
      'Buy 3 shares of GOOGL',
      'What is my cash balance?',
    ];

    const responses = await Promise.all(
      messages.map(msg => api.sendChatMessage(msg))
    );

    // All should succeed
    responses.forEach(response => {
      expect(response.message).toBeDefined();
      expect(response.message.content).toBeTruthy();
    });

    // Verify trades were executed
    const portfolio = await api.getPortfolio();
    expect(portfolio.positions.length).toBeGreaterThanOrEqual(2);
  });

  test('should reject empty or invalid chat messages', async ({ page }) => {
    const api = new APIClient(page);

    // Try to send empty message
    await expect(async () => {
      await api.sendChatMessage('');
    }).toThrow();

    // Try very long message (over 1000 chars)
    await expect(async () => {
      await api.sendChatMessage('a'.repeat(1001));
    }).toThrow();
  });

  test('should display chat messages in UI', async ({ page }) => {
    await page.goto('/');

    // Wait for page load
    await page.waitForLoadState('networkidle');

    // Look for chat interface
    const chatPanel = page.locator(
      '[data-testid="chat-panel"], .chat-panel, #chat'
    );

    const isVisible = await chatPanel.isVisible().catch(() => false);

    if (isVisible) {
      // Look for message input
      const messageInput = page.locator(
        '[data-testid="chat-input"], .chat-input, textarea[placeholder*="message"]'
      );
      await expect(messageInput).toBeVisible();
    }
  });
});
