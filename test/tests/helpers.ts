/**
 * Test helper utilities for FinAlly E2E tests
 */

import { Page, APIResponse } from '@playwright/test';

// API Types (matching backend contracts)
export interface PortfolioResponse {
  cash_balance: number;
  total_value: number;
  positions: Position[];
  total_unrealized_pl: number;
  total_unrealized_pl_percent: number;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  cost_basis: number;
  unrealized_pl: number;
  unrealized_pl_percent: number;
}

export interface WatchlistResponse {
  tickers: WatchlistItem[];
}

export interface WatchlistItem {
  ticker: string;
  price: number;
  change: number;
  change_percent: number;
  added_at: string;
}

export interface TradeRequest {
  ticker: string;
  quantity: number;
  side: 'buy' | 'sell';
}

export interface TradeResponse {
  status: 'executed';
  trade: {
    id: string;
    ticker: string;
    side: 'buy' | 'sell';
    quantity: number;
    price: number;
    total_value: number;
    executed_at: string;
  };
  portfolio: PortfolioResponse;
}

export interface ChatResponse {
  message: {
    id: string;
    role: 'assistant';
    content: string;
    created_at: string;
  };
  executed_actions: {
    trades: any[];
    watchlist_changes: any[];
  } | null;
}

/**
 * API Client helper for making backend requests
 */
export class APIClient {
  constructor(private page: Page) {}

  private async request(path: string, options?: RequestInit): Promise<APIResponse> {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';
    return await this.page.request.fetch(`${baseURL}${path}`, options);
  }

  async getPortfolio(): Promise<PortfolioResponse> {
    const response = await this.request('/api/portfolio');
    if (!response.ok()) {
      throw new Error(`Failed to fetch portfolio: ${response.status()}`);
    }
    return await response.json() as PortfolioResponse;
  }

  async getWatchlist(): Promise<WatchlistResponse> {
    const response = await this.request('/api/watchlist');
    if (!response.ok()) {
      throw new Error(`Failed to fetch watchlist: ${response.status()}`);
    }
    return await response.json() as WatchlistResponse;
  }

  async addToWatchlist(ticker: string): Promise<any> {
    const response = await this.request('/api/watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify({ ticker }),
    });
    if (!response.ok()) {
      const error = await response.json();
      throw new Error(`Failed to add ticker: ${JSON.stringify(error)}`);
    }
    return await response.json();
  }

  async removeFromWatchlist(ticker: string): Promise<any> {
    const response = await this.request(`/api/watchlist/${ticker}`, {
      method: 'DELETE',
    });
    if (!response.ok()) {
      const error = await response.json();
      throw new Error(`Failed to remove ticker: ${JSON.stringify(error)}`);
    }
    return await response.json();
  }

  async executeTrade(trade: TradeRequest): Promise<TradeResponse> {
    const response = await this.request('/api/portfolio/trade', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify(trade),
    });
    if (!response.ok()) {
      const error = await response.json();
      throw new Error(`Failed to execute trade: ${JSON.stringify(error)}`);
    }
    return await response.json() as TradeResponse;
  }

  async sendChatMessage(message: string): Promise<ChatResponse> {
    const response = await this.request('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify({ message }),
    });
    if (!response.ok()) {
      const error = await response.json();
      throw new Error(`Failed to send chat message: ${JSON.stringify(error)}`);
    }
    return await response.json() as ChatResponse;
  }

  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.request('/api/health');
      return response.ok();
    } catch {
      return false;
    }
  }
}

/**
 * Wait for SSE connection to be established
 */
export async function waitForSSEConnection(page: Page): Promise<void> {
  // Wait for connection status indicator to show green/connected
  await page.waitForSelector('[data-testid="connection-status"], .connection-status, [data-connection="connected"]', {
    timeout: 10000,
  }).catch(() => {
    // If no explicit connection indicator, wait for prices to appear
    return page.waitForSelector('[data-ticker-price], .ticker-price, [data-testid="watchlist-item"]', {
      timeout: 10000,
    });
  });
}

/**
 * Wait for price updates to start streaming
 */
export async function waitForPriceUpdates(page: Page, ticker?: string): Promise<void> {
  const selector = ticker
    ? `[data-ticker="${ticker}"] [data-ticker-price], [data-ticker="${ticker}"].price`
    : '[data-ticker-price], .ticker-price';

  // Wait for at least one price element to appear
  await page.waitForSelector(selector, { timeout: 10000 });

  // Wait a bit for SSE stream to start sending updates
  await page.waitForTimeout(1000);
}

/**
 * Default tickers from seed data
 */
export const DEFAULT_TICKERS = [
  'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA',
  'NVDA', 'META', 'JPM', 'V', 'NFLX'
];

/**
 * Default initial cash balance
 */
export const DEFAULT_CASH = 10000.0;

/**
 * Retry helper for flaky operations
 */
export async function retry<T>(
  fn: () => Promise<T>,
  options: { retries?: number; delay?: number } = {}
): Promise<T> {
  const { retries = 3, delay = 1000 } = options;
  let lastError: Error | undefined;

  for (let i = 0; i <= retries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (i < retries) {
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError;
}

/**
 * Wait for condition to be true
 */
export async function waitForCondition(
  condition: () => boolean | Promise<boolean>,
  options: { timeout?: number; interval?: number } = {}
): Promise<void> {
  const { timeout = 10000, interval = 100 } = options;
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    if (await condition()) {
      return;
    }
    await new Promise(resolve => setTimeout(resolve, interval));
  }

  throw new Error(`Condition not met within ${timeout}ms`);
}
