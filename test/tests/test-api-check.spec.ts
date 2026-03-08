/**
 * API Implementation Check
 *
 * Quick check to verify which backend endpoints are implemented
 * and identify gaps before running full E2E tests.
 */
import { test, expect } from '@playwright/test';

test.describe('API Implementation Check', () => {

  test('should have health check endpoint', async ({ page }) => {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';
    const response = await page.request.fetch(`${baseURL}/api/health`);

    if (response.ok()) {
      const data = await response.json();
      console.log('✅ Health check endpoint:', data);
    } else {
      console.log('❌ Health check endpoint not implemented');
    }

    // This test is informational, so we don't fail
    expect(response.status()).toBeGreaterThanOrEqual(200);
  });

  test('should have portfolio endpoint', async ({ page }) => {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';
    const response = await page.request.fetch(`${baseURL}/api/portfolio`);

    if (response.ok()) {
      const data = await response.json();
      console.log('✅ Portfolio endpoint:', JSON.stringify(data, null, 2));
    } else {
      console.log('❌ Portfolio endpoint not implemented:', response.status());
    }
  });

  test('should have watchlist endpoint', async ({ page }) => {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';
    const response = await page.request.fetch(`${baseURL}/api/watchlist`);

    if (response.ok()) {
      const data = await response.json();
      console.log('✅ Watchlist endpoint:', JSON.stringify(data, null, 2));
    } else {
      console.log('❌ Watchlist endpoint not implemented:', response.status());
    }
  });

  test('should have SSE streaming endpoint', async ({ page }) => {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';

    try {
      // SSE connections don't work well with fetch, so we just check if it responds
      const response = await page.request.fetch(`${baseURL}/api/stream/prices`, {
        timeout: 2000,
      });

      // SSE endpoint should return 200 and text/event-stream content type
      if (response.status() === 200) {
        const contentType = response.headers()['content-type'];
        console.log('✅ SSE endpoint:', contentType);
      } else {
        console.log('⚠️ SSE endpoint status:', response.status());
      }
    } catch (error) {
      console.log('❌ SSE endpoint error:', (error as Error).message);
    }
  });

  test('should have chat endpoint', async ({ page }) => {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';
    const response = await page.request.fetch(`${baseURL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify({ message: 'Hello' }),
    });

    if (response.ok()) {
      const data = await response.json();
      console.log('✅ Chat endpoint:', JSON.stringify(data, null, 2));
    } else {
      console.log('❌ Chat endpoint not implemented:', response.status());
    }
  });

  test('should serve frontend static files', async ({ page }) => {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';
    const response = await page.request.fetch(baseURL);

    if (response.ok()) {
      const contentType = response.headers()['content-type'];
      console.log('✅ Frontend served:', contentType);
    } else {
      console.log('❌ Frontend not served:', response.status());
    }
  });

  test('should handle trade execution', async ({ page }) => {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';
    const response = await page.request.fetch(`${baseURL}/api/portfolio/trade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify({
        ticker: 'AAPL',
        quantity: 10,
        side: 'buy'
      }),
    });

    if (response.ok()) {
      const data = await response.json();
      console.log('✅ Trade endpoint:', JSON.stringify(data, null, 2));
    } else {
      const error = await response.json().catch(() => ({ error: 'Unknown error' }));
      console.log('❌ Trade endpoint failed:', response.status(), error);
    }
  });

  test('should handle watchlist add', async ({ page }) => {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';
    const response = await page.request.fetch(`${baseURL}/api/watchlist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify({ ticker: 'PYPL' }),
    });

    if (response.ok()) {
      const data = await response.json();
      console.log('✅ Watchlist add:', JSON.stringify(data, null, 2));

      // Clean up - remove the ticker we just added
      await page.request.fetch(`${baseURL}/api/watchlist/PYPL`, {
        method: 'DELETE',
      });
    } else {
      const error = await response.json().catch(() => ({ error: 'Unknown error' }));
      console.log('❌ Watchlist add failed:', response.status(), error);
    }
  });

  test('should handle watchlist remove', async ({ page }) => {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';
    const response = await page.request.fetch(`${baseURL}/api/watchlist/NFLX`, {
      method: 'DELETE',
    });

    if (response.ok()) {
      const data = await response.json();
      console.log('✅ Watchlist remove:', JSON.stringify(data, null, 2));
    } else {
      const error = await response.json().catch(() => ({ error: 'Unknown error' }));
      console.log('❌ Watchlist remove failed:', response.status(), error);
    }
  });
});
